"""
Configuración central del backend. Lee .env una sola vez (lru_cache).

Orden de búsqueda del archivo .env (el primero que exista gana):
  1. ../.env  → .env único en la raíz del repositorio  ← recomendado
  2.   .env   → .env local dentro de backend/           ← fallback
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

# Raíz del repo (dos niveles arriba de este archivo)
_REPO_ROOT = Path(__file__).resolve().parent.parent
_ROOT_ENV  = _REPO_ROOT / ".env"
_LOCAL_ENV = Path(__file__).resolve().parent / ".env"

# Usa el .env de la raíz si existe; si no, el local de backend/
_ENV_FILE = str(_ROOT_ENV) if _ROOT_ENV.exists() else str(_LOCAL_ENV)


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str

    # Tools
    tavily_api_key: str
    usda_api_key: str = "DEMO_KEY"  # USDA permite DEMO_KEY con rate limit bajo

    # Firebase
    google_application_credentials: str = "./firebase-service-account.json"
    firebase_project_id: str

    # CORS
    cors_origins: str = "http://localhost:5173"  # comma-separated

    # Logging
    log_level: str = "INFO"

    model_config = {
        "env_file": _ENV_FILE,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
