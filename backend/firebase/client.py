"""
Firebase Admin SDK — inicialización del cliente Firestore async (singleton).

El SDK de Firebase Admin salta las Firestore rules; se conecta directamente
con los permisos del service account. Por eso las rules son deny-all para
clientes públicos: toda escritura/lectura pasa por aquí.
"""
from __future__ import annotations

import json
import os

import firebase_admin
from firebase_admin import credentials, firestore_async
from functools import lru_cache

from config import get_settings


@lru_cache(maxsize=1)
def _init_app() -> None:
    """Inicializa la app de Firebase una sola vez (idempotente)."""
    settings = get_settings()
    if firebase_admin._apps:
        return

    # Railway/entornos sin filesystem: JSON completo como variable de entorno.
    # En local sigue usando el archivo .json normalmente.
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
    else:
        cred = credentials.Certificate(settings.google_application_credentials)

    firebase_admin.initialize_app(
        cred,
        {"projectId": settings.firebase_project_id},
    )


def get_async_db():
    """Retorna el AsyncClient de Firestore (singleton a través del SDK)."""
    _init_app()
    return firestore_async.client()
