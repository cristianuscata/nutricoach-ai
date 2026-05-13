"""
Schemas Pydantic para request/response del API.

Separados de config.py para no mezclar configuración con contratos del API.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Clientes                                                                     #
# --------------------------------------------------------------------------- #

class ClientProfile(BaseModel):
    """Perfil médico-nutricional de un cliente."""
    name: str
    age: int
    sex: str
    height_cm: float
    weight_kg: float
    activity_level: str
    goals: list[str] = []
    dietary_restrictions: list[str] = []
    allergies: list[str] = []
    medical_conditions: list[str] = []
    medications: list[str] = []
    cultural_preferences: list[str] = []
    dislikes: list[str] = []
    language: str = "es"
    timezone: str = "America/Lima"
    notes: str = ""

    model_config = {"extra": "allow"}  # permite campos adicionales (biomarkers, etc.)


# --------------------------------------------------------------------------- #
# Conversaciones / Chat                                                        #
# --------------------------------------------------------------------------- #

class ChatMessage(BaseModel):
    role: str          # "human" | "ai" | "system"
    content: str
    ts: str | None = None


class ConversationSummary(BaseModel):
    conversation_id: str
    client_id: str
    updated_at: str | None = None
    message_count: int = 0


# --------------------------------------------------------------------------- #
# Respuestas del agente (SSE events)                                          #
# --------------------------------------------------------------------------- #

class MetaEvent(BaseModel):
    conversation_id: str
    model_used: str
    routing_reason: str


class TokenEvent(BaseModel):
    content: str


class ToolCallEvent(BaseModel):
    tool: str
    input: dict[str, Any] = {}


class DoneEvent(BaseModel):
    conversation_id: str


class ErrorEvent(BaseModel):
    detail: str


# --------------------------------------------------------------------------- #
# Health                                                                       #
# --------------------------------------------------------------------------- #

class HealthResponse(BaseModel):
    status: str = "ok"
