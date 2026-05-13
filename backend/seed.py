"""
Script de carga inicial de perfiles en Firestore.

Uso:
    cd backend
    python seed.py

Lee data/seed_clients.json y hace upsert de cada cliente en la colección
`clients`. Seguro de re-ejecutar (merge=True, no borra datos existentes).
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore_async

from config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


async def seed() -> None:
    settings = get_settings()

    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.google_application_credentials)
        firebase_admin.initialize_app(
            cred, {"projectId": settings.firebase_project_id}
        )

    db = firestore_async.client()

    data_path = Path(__file__).parent / "data" / "seed_clients.json"
    clients: list[dict] = json.loads(data_path.read_text(encoding="utf-8"))

    for raw in clients:
        client_id = raw.pop("client_id")
        await db.collection("clients").document(client_id).set(raw, merge=True)
        logger.info("✔  Seeded  client_id=%-12s  name=%s", client_id, raw.get("name"))

    logger.info("Done — %d clientes cargados.", len(clients))


if __name__ == "__main__":
    asyncio.run(seed())
