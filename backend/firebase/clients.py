"""
CRUD sobre la colección `clients` de Firestore.

Cada documento tiene como ID el `client_id` y almacena el perfil
médico-nutricional del cliente tal como está definido en seed_clients.json.
"""
from __future__ import annotations

from typing import Any

from google.cloud.firestore import AsyncClient

CLIENTS_COLLECTION = "clients"


async def get_client(db: AsyncClient, client_id: str) -> dict[str, Any] | None:
    """Lee un cliente por ID. Retorna None si no existe."""
    doc = await db.collection(CLIENTS_COLLECTION).document(client_id).get()
    if not doc.exists:
        return None
    return {"client_id": doc.id, **doc.to_dict()}


async def list_clients(db: AsyncClient) -> list[dict[str, Any]]:
    """Lista todos los clientes de la colección."""
    clients: list[dict[str, Any]] = []
    async for doc in db.collection(CLIENTS_COLLECTION).stream():
        clients.append({"client_id": doc.id, **doc.to_dict()})
    return clients


async def upsert_client(
    db: AsyncClient, client_id: str, data: dict[str, Any]
) -> None:
    """Crea o actualiza un cliente (merge=True para no borrar campos existentes)."""
    await db.collection(CLIENTS_COLLECTION).document(client_id).set(
        data, merge=True
    )


async def delete_client(db: AsyncClient, client_id: str) -> None:
    """Elimina un cliente. No lanza si no existe."""
    await db.collection(CLIENTS_COLLECTION).document(client_id).delete()
