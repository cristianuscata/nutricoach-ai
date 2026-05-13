"""
Punto de entrada FastAPI para NutriCoach.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings

# Routers
from routers.agent_router import router as agent_router
from routers.clients_router import router as clients_router

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)

app = FastAPI(
    title="NutriCoach API",
    version="1.0.0",
    description="Asistente nutricional con memoria persistente y datos USDA en tiempo real.",
)

# CORS — restrictivo en producción
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Liveness probe. Cloud Run lo usa para health checks."""
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"service": "NutriCoach", "version": app.version, "docs": "/docs"}


app.include_router(clients_router)
app.include_router(agent_router)
