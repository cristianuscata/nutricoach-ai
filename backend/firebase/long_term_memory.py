"""
Memoria de largo plazo: extracción y recuperación de hechos del cliente.

Por qué este módulo existe
--------------------------
La guía base propone "memoria persistente" = guardar todos los mensajes en
un array Firestore. Eso es un *log*, no una memoria.

Una memoria real cumple dos cosas que un log no:

1. **Sobrevive al límite del documento (1 MB)**: cuando una conversación
   crece, no podemos seguir agregando mensajes. Necesitamos compactar.

2. **Sobrevive entre conversaciones distintas**: si Ana abre una conversación
   nueva la próxima semana, el agente debería saber que la semana pasada le
   recomendó arroz integral y que Ana reportó que le funcionó. Eso no está
   en el array de la nueva conversación.

Diseño
------
Colección `client_facts` en Firestore con un documento por cliente:

    client_facts/{client_id}
        facts: [
            { text: "Reporta hinchazón con lácteos", source_conv: "...", date: ... },
            { text: "Le funcionó arroz integral en cenas", ... },
            { text: "Toma agua suficiente, ya no hay que recordárselo", ... }
        ]
        running_summary: "Ana lleva 3 semanas en plan hipocalórico..."
        updated_at: ...

Cuándo se actualiza
-------------------
Después de cada turno completo (mensaje del usuario + respuesta del agente),
disparamos una **background task** que:

1. Le pide a `gpt-5-mini` (barato) que extraiga hechos nuevos del turno.
2. Hace dedup contra los facts existentes.
3. Actualiza Firestore.

Esto NO bloquea la respuesta al usuario. El costo se amortiza fuera del
path crítico.

Trade-off
---------
- Plus: contexto persistente real entre sesiones.
- Minus: costo extra de ~$0.0005 por turno (gpt-5-mini, ~500 tokens).
- Mitigación: solo extraer cada N=3 turnos en conversaciones largas.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from google.cloud.firestore import AsyncClient, ArrayUnion
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_settings

logger = logging.getLogger(__name__)

FACTS_COLLECTION = "client_facts"
MAX_FACTS_PER_CLIENT = 50  # Cap para no inflar el system prompt


# --------------------------------------------------------------------------- #
# Lectura                                                                     #
# --------------------------------------------------------------------------- #

async def get_client_facts(db: AsyncClient, client_id: str) -> dict[str, Any]:
    """
    Lee los facts de largo plazo de un cliente.

    Returns
    -------
    {
      "facts": [str, ...],
      "running_summary": str,
      "updated_at": iso-string | None
    }
    """
    doc = await db.collection(FACTS_COLLECTION).document(client_id).get()
    if not doc.exists:
        return {"facts": [], "running_summary": "", "updated_at": None}

    data = doc.to_dict() or {}
    return {
        "facts": [f["text"] for f in data.get("facts", [])][-MAX_FACTS_PER_CLIENT:],
        "running_summary": data.get("running_summary", ""),
        "updated_at": data.get("updated_at"),
    }


def format_facts_for_prompt(facts_data: dict[str, Any]) -> str:
    """Formatea los facts para inyectarlos en el system prompt."""
    facts = facts_data.get("facts", [])
    summary = facts_data.get("running_summary", "")

    if not facts and not summary:
        return "(Sin información previa de largo plazo.)"

    parts = []
    if summary:
        parts.append(f"Resumen de la relación con el cliente:\n{summary}")
    if facts:
        bullets = "\n".join(f"- {f}" for f in facts)
        parts.append(f"Hechos relevantes recordados:\n{bullets}")
    return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# Extracción (background task)                                                #
# --------------------------------------------------------------------------- #

_EXTRACTION_PROMPT = """Eres un asistente que extrae hechos relevantes de largo plazo
sobre un cliente de un servicio de coaching nutricional.

Te paso el último intercambio entre el usuario y el coach. Tu trabajo:

1. Identificar hechos NUEVOS sobre el cliente que valga la pena recordar a futuro.
   Ejemplos válidos: "reportó hinchazón con lácteos", "no le gustó la quinoa",
   "logró 3 días seguidos de meal prep", "le pidieron rebajar 4kg para boda en agosto".
2. Ignorar lo trivial: saludos, preguntas técnicas resueltas, datos que ya están
   en el perfil estructurado (alergias, condiciones, nombre).
3. Devolver una lista JSON de strings cortos, en español, en tercera persona.
   Si no hay nada que valga la pena, devolver lista vacía: [].

Hechos ya conocidos del cliente (no repetir):
{existing_facts}

Intercambio reciente:
USUARIO: {user_message}
COACH: {assistant_message}

Responde SOLO con un JSON array. Ejemplo: ["fact 1", "fact 2"] o []."""


async def extract_and_store_facts(
    db: AsyncClient,
    client_id: str,
    user_message: str,
    assistant_message: str,
    existing_facts: list[str],
    conversation_id: str,
) -> list[str]:
    """
    Extrae hechos nuevos del turno y los persiste.

    Diseñado para correr como background task. No debe lanzar — si falla,
    se loguea y se sigue.

    Returns
    -------
    Lista de facts nuevos extraídos (puede estar vacía).
    """
    settings = get_settings()
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.openai_api_key,
        temperature=0.0,
        max_tokens=400,
    )

    prompt = _EXTRACTION_PROMPT.format(
        existing_facts="\n".join(f"- {f}" for f in existing_facts) or "(ninguno)",
        user_message=user_message[:1500],
        assistant_message=assistant_message[:2500],
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content="Eres un extractor de hechos. Solo respondes JSON."),
            HumanMessage(content=prompt),
        ])
        raw = (response.content or "").strip()
        # Limpiar fences markdown si los agregó
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        new_facts = json.loads(raw.strip())
        if not isinstance(new_facts, list):
            return []
        new_facts = [str(f).strip() for f in new_facts if str(f).strip()][:5]
    except (json.JSONDecodeError, IndexError, ValueError) as e:
        logger.warning(
            "fact_extraction_parse_error client_id=%s err=%s",
            client_id, e,
        )
        return []
    except Exception as e:
        logger.warning(
            "fact_extraction_llm_error client_id=%s err=%s",
            client_id, e,
        )
        return []

    if not new_facts:
        return []

    # Persistir
    now = datetime.now(timezone.utc).isoformat()
    fact_objects = [
        {"text": f, "source_conv": conversation_id, "date": now}
        for f in new_facts
    ]

    doc_ref = db.collection(FACTS_COLLECTION).document(client_id)
    await doc_ref.set(
        {
            "facts": ArrayUnion(fact_objects),
            "updated_at": now,
        },
        merge=True,
    )

    logger.info(
        "fact_extraction_saved client_id=%s count=%d",
        client_id, len(new_facts),
    )
    return new_facts


# --------------------------------------------------------------------------- #
# Compactación de mensajes (cuando la conversación se hace larga)             #
# --------------------------------------------------------------------------- #

async def maybe_compact_conversation(
    db: AsyncClient,
    conversation_id: str,
    threshold: int = 60,
) -> None:
    """
    Si la conversación supera `threshold` mensajes, comprime la primera mitad
    a un resumen y reemplaza esos mensajes con un único `system` de resumen.

    Esto previene tocar el límite de 1 MB del documento Firestore en sesiones
    muy largas, manteniendo continuidad semántica.

    Llamar como background task, no en path crítico.
    """
    doc = await db.collection("conversations").document(conversation_id).get()
    if not doc.exists:
        return

    data = doc.to_dict() or {}
    messages = data.get("messages", [])
    if len(messages) < threshold:
        return

    half = len(messages) // 2
    to_compact = messages[:half]
    to_keep = messages[half:]

    settings = get_settings()
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.openai_api_key,
        temperature=0.0,
        max_tokens=600,
    )

    transcript = "\n".join(
        f"[{m['role']}] {m['content'][:500]}" for m in to_compact
    )
    prompt = (
        "Resume el siguiente fragmento de conversación entre un usuario y un "
        "coach nutricional, preservando: temas tratados, recomendaciones dadas, "
        "preferencias del usuario reveladas, decisiones tomadas. Sé conciso "
        "(máximo 250 palabras) en español.\n\n" + transcript
    )

    try:
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        summary = resp.content
    except Exception as e:
        logger.warning("compact_llm_error conv=%s err=%s", conversation_id, e)
        return

    new_messages = [
        {"role": "system", "content": f"[Resumen de turnos previos]\n{summary}"}
    ] + to_keep

    await db.collection("conversations").document(conversation_id).update({
        "messages": new_messages,
        "compacted_at": datetime.now(timezone.utc).isoformat(),
    })

    logger.info(
        "conversation_compacted conv=%s old_count=%d new_count=%d",
        conversation_id, len(messages), len(new_messages),
    )
