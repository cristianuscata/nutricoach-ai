"""
Endpoints del agente: chat (SSE) y listado de conversaciones.

Diferencias clave vs la guía base
---------------------------------
1. **Heartbeats SSE**: enviamos un comentario `: keepalive` cada 15s para evitar
   que Cloud Run u otros proxies cierren la conexión por idle.
2. **Header X-Accel-Buffering: no**: previene buffering del proxy que rompe SSE.
3. **Rate limit por client_id**: protección básica contra abuso.
4. **Background task de extracción de facts**: la memoria de largo plazo se
   actualiza fuera del path crítico.
5. **Detección de tool use para el modelo router**: leemos los eventos del
   stream y marcamos `last_assistant_used_tool` para el siguiente turno.
6. **Logging seguro**: nunca logueamos contenido del usuario/asistente sin
   pasarlo por `safe_log`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from typing import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from agent.agent import build_chat_history, create_agent
from agent.model_router import route as route_model
from firebase.chat_history import (
    add_message,
    create_conversation,
    get_conversation,
    get_conversations_for_client,
)
from firebase.client import get_async_db
from firebase.clients import get_client
from firebase.long_term_memory import (
    extract_and_store_facts,
    format_facts_for_prompt,
    get_client_facts,
    maybe_compact_conversation,
)
from security.guardrails import (
    GuardrailRejection,
    safe_log,
    sanitize_user_input,
    wrap_user_input_for_llm,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------- #
# Rate limiting (in-memory, por client_id)                                    #
# --------------------------------------------------------------------------- #
# Para producción real con múltiples instancias usar Redis/Memcached.
# Para Cloud Run con 1 instancia mínima, esto basta.
_RATE_WINDOW_SEC = 60
_RATE_MAX_REQS = 15
_rate_store: dict[str, deque[float]] = defaultdict(deque)


def _check_rate_limit(client_id: str) -> bool:
    now = time.time()
    window = _rate_store[client_id]
    while window and window[0] < now - _RATE_WINDOW_SEC:
        window.popleft()
    if len(window) >= _RATE_MAX_REQS:
        return False
    window.append(now)
    return True


# --------------------------------------------------------------------------- #
# Tracking de uso de tool por conversación (para el model router)             #
# --------------------------------------------------------------------------- #
# Mapa conversation_id -> bool. Se setea en True cuando el último turno usó tool.
# Se resetea cuando empieza un nuevo turno.
_last_used_tool: dict[str, bool] = {}


# --------------------------------------------------------------------------- #
# /agent/conversations                                                        #
# --------------------------------------------------------------------------- #

@router.get("/agent/conversations")
async def list_conversations(client_id: str):
    """Lista las conversaciones de un cliente para el sidebar del frontend."""
    db = get_async_db()
    convs = await get_conversations_for_client(db, client_id)
    return {"conversations": convs}


@router.get("/agent/conversations/{conversation_id}")
async def fetch_conversation(conversation_id: str):
    db = get_async_db()
    conv = await get_conversation(db, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return conv


# --------------------------------------------------------------------------- #
# /agent/stream — el endpoint principal                                       #
# --------------------------------------------------------------------------- #

@router.get("/agent/stream")
async def stream_agent(
    background_tasks: BackgroundTasks,
    client_id: str = Query(...),
    message: str = Query(...),
    conversation_id: str | None = Query(None),
):
    """
    Server-Sent Events: streamea tokens del agente para un turno.

    Eventos emitidos al cliente:
    - `event: meta`          { conversation_id, model_used }
    - `event: tool_call`     { tool, query }
    - `event: token`         { content }
    - `event: done`          { conversation_id }
    - `event: error`         { detail }
    """
    # 0. Rate limit
    if not _check_rate_limit(client_id):
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    # 1. Sanitizar input
    try:
        sanitized = sanitize_user_input(message, client_id)
    except GuardrailRejection as e:
        raise HTTPException(status_code=400, detail=f"rejected: {e}")

    db = get_async_db()

    # 2. Cargar perfil (si no existe, 404 antes de pagar tokens)
    client = await get_client(db, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")

    # 3. Crear o continuar conversación
    if not conversation_id:
        conversation_id = await create_conversation(db, client_id)

    await add_message(db, conversation_id, "human", sanitized)

    # 4. Cargar historial corto + memoria larga
    conv = await get_conversation(db, conversation_id)
    history = conv.get("messages", [])[:-1]  # excluyo el mensaje recién agregado
    chat_history = build_chat_history(history)

    facts_data = await get_client_facts(db, client_id)
    long_term_str = format_facts_for_prompt(facts_data)

    # 5. Decidir modelo
    routing = route_model(
        user_message=sanitized,
        last_assistant_used_tool=_last_used_tool.get(conversation_id, False),
        conversation_message_count=len(history),
    )
    logger.info(
        "routing client_id=%s conv=%s model=%s reason=%s msg=%s",
        client_id, conversation_id, routing.model.value, routing.reason,
        safe_log(sanitized, 80),
    )

    # 6. Resetear tracker de tool para este turno
    _last_used_tool[conversation_id] = False

    # 7. Construir agente
    executor = create_agent(client, long_term_str, routing)

    wrapped_input = wrap_user_input_for_llm(sanitized)

    async def event_generator() -> AsyncGenerator[dict, None]:
        full_response_parts: list[str] = []
        keepalive_task: asyncio.Task | None = None

        # Heartbeat para evitar que el proxy cierre la conexión
        async def keepalive_loop():
            try:
                while True:
                    await asyncio.sleep(15)
                    yield_queue.put_nowait({"event": "ping", "data": "{}"})
            except asyncio.CancelledError:
                pass

        # Cola para multiplexar tokens reales + heartbeats
        yield_queue: asyncio.Queue = asyncio.Queue()

        async def producer():
            try:
                # Meta inicial: cliente sabe qué modelo se está usando
                await yield_queue.put({
                    "event": "meta",
                    "data": json.dumps({
                        "conversation_id": conversation_id,
                        "model_used": routing.model.value,
                        "routing_reason": routing.reason,
                    }),
                })

                async for event in executor.astream_events(
                    {"input": wrapped_input, "chat_history": chat_history},
                    version="v2",
                ):
                    ev_type = event.get("event")

                    if ev_type == "on_chat_model_stream":
                        chunk = event["data"].get("chunk")
                        if chunk and chunk.content:
                            full_response_parts.append(chunk.content)
                            await yield_queue.put({
                                "event": "token",
                                "data": json.dumps({"content": chunk.content}),
                            })

                    elif ev_type == "on_tool_start":
                        _last_used_tool[conversation_id] = True
                        await yield_queue.put({
                            "event": "tool_call",
                            "data": json.dumps({
                                "tool": event.get("name", "tool"),
                                "input": event.get("data", {}).get("input", {}),
                            }),
                        })

                full_response = "".join(full_response_parts)

                # Persistir respuesta del agente
                await add_message(db, conversation_id, "ai", full_response)

                # Disparar background tasks (no bloquean al usuario)
                background_tasks.add_task(
                    extract_and_store_facts,
                    db, client_id, sanitized, full_response,
                    facts_data["facts"], conversation_id,
                )
                background_tasks.add_task(
                    maybe_compact_conversation, db, conversation_id,
                )

                await yield_queue.put({
                    "event": "done",
                    "data": json.dumps({
                        "conversation_id": conversation_id,
                    }),
                })

            except Exception as e:
                logger.exception(
                    "agent_stream_error client_id=%s conv=%s",
                    client_id, conversation_id,
                )
                await yield_queue.put({
                    "event": "error",
                    "data": json.dumps({"detail": str(e)[:200]}),
                })
            finally:
                # Sentinel para que el consumidor termine
                await yield_queue.put(None)

        async def heartbeat():
            try:
                while True:
                    await asyncio.sleep(15)
                    await yield_queue.put({
                        "event": "ping",
                        "data": "{}",
                    })
            except asyncio.CancelledError:
                pass

        prod_task = asyncio.create_task(producer())
        hb_task = asyncio.create_task(heartbeat())

        try:
            while True:
                item = await yield_queue.get()
                if item is None:
                    break
                yield item
        finally:
            hb_task.cancel()
            prod_task.cancel()
            try:
                await hb_task
            except asyncio.CancelledError:
                pass

    # Headers críticos para SSE en Cloud Run / nginx / Cloudflare
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return EventSourceResponse(event_generator(), headers=headers)
