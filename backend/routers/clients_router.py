"""
Router de clientes: CRUD expuesto al frontend.

Endpoints:
    GET  /clients                → lista todos
    GET  /clients/{client_id}   → perfil de uno
    POST /clients/{client_id}   → crea o actualiza
    DELETE /clients/{client_id} → elimina
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from firebase.client import get_async_db
from firebase.clients import delete_client, get_client, list_clients, upsert_client

router = APIRouter()


@router.get("/clients")
async def get_clients():
    """Lista todos los clientes registrados."""
    db = get_async_db()
    clients = await list_clients(db)
    return {"clients": clients}


@router.get("/clients/{client_id}")
async def get_single_client(client_id: str):
    """Retorna el perfil de un cliente. 404 si no existe."""
    db = get_async_db()
    client = await get_client(db, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")
    return client


@router.post("/clients/{client_id}")
async def create_or_update_client(client_id: str, data: dict[str, Any]):
    """
    Crea o actualiza el perfil de un cliente (merge).

    El body JSON es el perfil completo o parcial; campos no enviados
    se conservan en Firestore.
    """
    db = get_async_db()
    await upsert_client(db, client_id, data)
    return {"status": "ok", "client_id": client_id}


@router.delete("/clients/{client_id}")
async def remove_client(client_id: str):
    """Elimina un cliente. Idempotente (no lanza si ya fue eliminado)."""
    db = get_async_db()
    await delete_client(db, client_id)
    return {"status": "deleted", "client_id": client_id}
