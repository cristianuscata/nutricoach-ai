"""
Model Router — Selección dinámica de modelo según complejidad estimada del turno.

Motivación
----------
Usar siempre `gpt-5` o `gpt-4.1` para chat conversacional es desperdicio. La mayoría
de los turnos son saludos, follow-ups cortos o aclaraciones que `gpt-5-mini` resuelve
con calidad equivalente a 1/5 del costo. Solo escalamos cuando:

1. El turno requiere uso de tools (razonamiento + integración de fuentes externas).
2. El usuario pide un meal plan, análisis de biomarcadores o explicación profunda.
3. El historial reciente sugiere conversación compleja (último turno usó tool).

El router es heurístico, no llama a otro LLM (eso anularía el ahorro). Es
intencionalmente conservador: ante la duda, escala al modelo grande.

Política de escalado
--------------------
- Default: `gpt-5-mini`
- Trigger keywords: "plan", "menú", "receta", "biomarcador", "análisis", "compara"
- Heurística de longitud: mensajes > 200 chars suelen requerir respuestas elaboradas
- Heurística de tool: si el último turno asistente usó tool, este probablemente
  también lo hará (continuidad temática)

Métricas a monitorear (Cloud Logging)
-------------------------------------
- % de turnos en cada tier
- Latencia P50/P95 por tier
- Costo agregado por client_id

Trade-off
---------
Heurística simple < clasificador entrenado < otro LLM. Elegimos heurística porque
el costo de un clasificador (latencia + entrenamiento) supera al ahorro a esta
escala. Cuando el proyecto crezca, migrar a un router basado en embeddings.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from enum import Enum


class ModelTier(str, Enum):
    FAST = "gpt-4o-mini"  # $0.15 in / $0.60 out por 1M
    SMART = "gpt-4o"       # $2.50 in / $10.00 out por 1M


@dataclass(frozen=True)
class RoutingDecision:
    model: ModelTier
    reason: str
    temperature: float


# Palabras clave que sugieren razonamiento profundo o uso de tools
_COMPLEX_KEYWORDS = re.compile(
    r"\b("
    r"plan|men[uú]|receta|recipe|"
    r"biomarcador|colesterol|glucosa|hemoglobina|"
    r"compar[aoe]|comparar|"
    r"an[aá]lisis|analiza|analizar|"
    r"calorias|calor[ií]as|macros|macronutrientes|"
    r"alergia|intolerancia|recall|"
    r"deficien|d[eé]ficit|"
    r"qu[eé] opin[oa]s|recom[ie]nd[oa]s"
    r")\b",
    re.IGNORECASE,
)

# Palabras que indican intención de búsqueda externa
_TOOL_HINT_KEYWORDS = re.compile(
    r"\b(busca|buscar|cu[aá]nt[oa]s? (calor[ií]as|prote[ií]nas?|carbs?)|"
    r"qu[eé] tiene|composici[oó]n|nutrientes? de|valor nutricional)\b",
    re.IGNORECASE,
)


def route(
    user_message: str,
    last_assistant_used_tool: bool = False,
    conversation_message_count: int = 0,
) -> RoutingDecision:
    """
    Decide qué modelo usar para este turno.

    Parameters
    ----------
    user_message : str
        El mensaje crudo del usuario para este turno.
    last_assistant_used_tool : bool
        True si el último turno del asistente invocó una tool. Continuidad temática.
    conversation_message_count : int
        Cantidad de mensajes en la conversación actual. Conversaciones largas
        tienden a profundizar.

    Returns
    -------
    RoutingDecision
    """
    msg = user_message.strip()
    msg_len = len(msg)

    # Heurística 1: continuidad temática con tool
    if last_assistant_used_tool:
        return RoutingDecision(
            model=ModelTier.SMART,
            reason="last_turn_used_tool",
            temperature=0.4,
        )

    # Heurística 2: keywords de complejidad
    if _COMPLEX_KEYWORDS.search(msg):
        return RoutingDecision(
            model=ModelTier.SMART,
            reason="complex_keyword_match",
            temperature=0.3,
        )

    # Heurística 3: hint de búsqueda externa
    if _TOOL_HINT_KEYWORDS.search(msg):
        return RoutingDecision(
            model=ModelTier.SMART,
            reason="tool_hint_match",
            temperature=0.3,
        )

    # Heurística 4: mensaje largo = pregunta elaborada
    if msg_len > 250:
        return RoutingDecision(
            model=ModelTier.SMART,
            reason="long_user_message",
            temperature=0.5,
        )

    # Default: rápido y barato
    return RoutingDecision(
        model=ModelTier.FAST,
        reason="default_simple_chat",
        temperature=0.7,
    )
