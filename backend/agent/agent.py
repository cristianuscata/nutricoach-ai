"""
Agente NutriCoach.

Compone:
- System prompt con perfil estructurado del cliente + facts de largo plazo.
- Reglas de seguridad inmutables (anti-injection, no-diagnosis).
- Tools de USDA y Tavily.
- Modelo seleccionado dinámicamente vía model_router.
"""
from __future__ import annotations

import json
from typing import Any

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from agent.model_router import ModelTier, RoutingDecision
from agent.tools_langchain import ALL_TOOLS
from config import get_settings
from security.guardrails import INJECTION_DEFENSE_FRAGMENT


SYSTEM_TEMPLATE = """\
Eres **NutriCoach**, un coach nutricional digital para usuarios hispanohablantes.

Tu propósito: ayudar al cliente a mejorar su alimentación de forma personalizada,
basándote en su perfil, historial reciente y datos nutricionales autoritativos.

# PERFIL DEL CLIENTE
Estos son datos estructurados verificados sobre el cliente. Úsalos siempre.

```json
{client_profile_json}
```

# MEMORIA DE LARGO PLAZO
Información relevante recordada de sesiones previas:

{long_term_memory}

# REGLAS DE COMPORTAMIENTO

1. **Personalización obligatoria**: Cada respuesta debe reflejar al menos un
   dato del perfil o de la memoria. Llamá al cliente por su nombre cuando sea
   natural, pero no en cada mensaje (sería robótico).

2. **Datos cuantitativos: usa la herramienta**. Si el usuario te pregunta por
   calorías, macros, micronutrientes o composición de un alimento, **DEBES**
   llamar a `get_nutrition_facts` antes de responder. Nunca inventes números.
   Cita la fuente USDA en tu respuesta.

3. **Información actual: usa la otra herramienta**. Para recalls, noticias o
   evidencia reciente, usá `search_health_news`.

4. **Estilo**: conciso, accionable, en español neutro. Cuando recomiendes,
   da pasos concretos (qué comer, cuánto, cuándo). Evita discursos largos.

5. **Adherencia cultural**: si el cliente tiene `cultural_preferences`,
   prioriza ingredientes y preparaciones de esa cuisine.

6. **Restricciones**: jamás recomiendes algo que viole `dietary_restrictions`
   o `allergies`. Si el usuario te pide algo que las viola, decí por qué y
   ofrece alternativa.

{injection_defense}

# FORMATO DE RESPUESTA

- Conversación breve: párrafo corto, sin headers.
- Plan o lista: usa bullets concisos.
- Datos nutricionales: tabla simple si comparas dos+ alimentos.
- Si vas a usar una tool, hazlo en silencio (el sistema ya muestra un loader
  al usuario); no anuncies "voy a buscar".
"""


def _build_system_prompt(client: dict[str, Any], long_term_memory: str) -> str:
    profile_json = json.dumps(
        {k: v for k, v in client.items() if k != "client_id"},
        ensure_ascii=False,
        indent=2,
    )
    resolved = SYSTEM_TEMPLATE.format(
        client_profile_json=profile_json,
        long_term_memory=long_term_memory or "(Sin información previa.)",
        injection_defense=INJECTION_DEFENSE_FRAGMENT,
    )
    # Escapar llaves restantes (del JSON) para que ChatPromptTemplate
    # no las interprete como variables de plantilla.
    return resolved.replace("{", "{{").replace("}", "}}")


def build_chat_history(messages: list[dict[str, Any]]) -> list:
    """Convierte mensajes Firestore en LangChain messages."""
    history = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "human":
            history.append(HumanMessage(content=content))
        elif role == "ai":
            history.append(AIMessage(content=content))
        # 'system' (resúmenes de compactación) → se ignoran en el array de historial,
        # ya están reflejados en el system prompt vía long_term_memory si aplica.
    return history


def create_agent(
    client: dict[str, Any],
    long_term_memory: str,
    routing: RoutingDecision,
) -> AgentExecutor:
    """
    Construye un AgentExecutor configurado para este cliente y este turno.

    Parameters
    ----------
    client : dict
        Perfil del cliente (de Firestore).
    long_term_memory : str
        String ya formateado con facts y running summary.
    routing : RoutingDecision
        Decisión del model_router para este turno.
    """
    settings = get_settings()

    llm = ChatOpenAI(
        model=routing.model.value,
        api_key=settings.openai_api_key,
        temperature=routing.temperature,
        streaming=True,
        # Cap de tokens: protección contra respuestas runaway
        max_tokens=1500,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", _build_system_prompt(client, long_term_memory)),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    agent = create_openai_tools_agent(llm, ALL_TOOLS, prompt)

    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=5,
        # Prevenir loops costosos
        max_execution_time=45.0,
        return_intermediate_steps=False,
    )
