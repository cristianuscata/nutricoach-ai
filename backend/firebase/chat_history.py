"""
CRUD de conversaciones y mensajes de chat en Firestore.

Colección: `conversations`
Documento: {
    client_id: str,
    messages: [{ role, content, ts }],
    created_at: iso-str,
    updated_at: iso-str,
}

El array `messages` crece con cada turno (human + ai).
`maybe_compact_conversation` en long_term_memory.py se encarga de comprimir
cuando el documento se acerca al límite de 1 MB.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from google.cloud.firestore import ArrayUnion, AsyncClient, Query

CONVERSATIONS_COLLECTION = "conversations"


async def create_conversation(db: AsyncClient, client_id: str) -> str:
    """Crea una nueva conversación y retorna su ID."""
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.collection(CONVERSATIONS_COLLECTION).document(conv_id).set({
        "client_id": client_id,
        "messages": [],
        "created_at": now,
        "updated_at": now,
    })
    return conv_id


async def get_conversation(
    db: AsyncClient, conversation_id: str
) -> dict[str, Any] | None:
    """Lee una conversación por ID. Retorna None si no existe."""
    doc = await db.collection(CONVERSATIONS_COLLECTION).document(conversation_id).get()
    if not doc.exists:
        return None
    return {"conversation_id": doc.id, **doc.to_dict()}


async def add_message(
    db: AsyncClient,
    conversation_id: str,
    role: str,
    content: str,
) -> None:
    """
    Agrega un mensaje al array `messages` de la conversación.

    Parameters
    ----------
    role : str
        "human" | "ai" | "system"
    content : str
        Texto del mensaje.
    """
    now = datetime.now(timezone.utc).isoformat()
    await db.collection(CONVERSATIONS_COLLECTION).document(conversation_id).update({
        "messages": ArrayUnion([{"role": role, "content": content, "ts": now}]),
        "updated_at": now,
    })


async def get_conversations_for_client(
    db: AsyncClient, client_id: str
) -> list[dict[str, Any]]:
    """
    Lista las conversaciones de un cliente, ordenadas por actividad reciente.

    Requiere índice compuesto en Firestore:
        client_id ASC + updated_at DESC
    Si no existe, Firestore devuelve un link en el error para crearlo.
    """
    query = (
        db.collection(CONVERSATIONS_COLLECTION)
        .where("client_id", "==", client_id)
        .order_by("updated_at", direction=Query.DESCENDING)
        .limit(20)
    )
    convs: list[dict[str, Any]] = []
    async for doc in query.stream():
        data = doc.to_dict() or {}
        convs.append({
            "conversation_id": doc.id,
            "client_id": data.get("client_id"),
            "updated_at": data.get("updated_at"),
            "message_count": len(data.get("messages", [])),
        })
    return convs
