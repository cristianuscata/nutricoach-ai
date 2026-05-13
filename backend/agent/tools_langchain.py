"""
Registro LangChain de las herramientas del agente.

Lección aprendida: la docstring de @tool ES el prompt que ve el LLM para decidir
si usar la herramienta. Aquí no se ahorra texto — al contrario, se gana
precisión. Los ejemplos concretos del dominio nutrición previenen que el LLM:

- Use Tavily cuando debería usar USDA (datos nutricionales cuantitativos).
- Use USDA cuando debería usar Tavily (recalls, noticias, evidencia reciente).
- No use ninguna y alucine valores nutricionales.
"""
from __future__ import annotations

from langchain_core.tools import tool

from tools.nutrition_tools import (
    format_tavily_results_for_llm,
    format_usda_results_for_llm,
    tavily_search_async,
    usda_search,
)


@tool
async def get_nutrition_facts(food_query: str) -> str:
    """
    Obtiene la composición nutricional autoritativa de un alimento desde USDA
    FoodData Central. Úsala SIEMPRE que el usuario pregunte por:

    - Calorías, macronutrientes (proteína, grasa, carbos) o micronutrientes
      de un alimento específico.
    - Comparación nutricional entre dos alimentos.
    - Composición de un producto branded (ej. "yogur Activia", "leche Gloria").
    - Aporte de fibra, sodio, hierro, calcio, vitamina B12, etc.

    Ejemplos de cuándo usarla:
    - "¿Cuántas calorías tiene la palta?"
    - "¿Qué tiene más proteína, lentejas o garbanzos?"
    - "Necesito el sodio de la sopa Maggi de pollo."
    - "Quiero subir hierro, dame opciones con buen aporte."

    NO la uses para:
    - Recetas o meal plans (esos los generas tú directamente).
    - Recalls o noticias de seguridad alimentaria (usa search_health_news).
    - Evidencia científica reciente (usa search_health_news).

    Args:
        food_query: Nombre del alimento en lenguaje natural. Funciona mejor en
                    inglés (ej. "avocado raw", "lentils cooked"), pero acepta
                    español. Si el usuario menciona varios, llama la tool una
                    vez por cada alimento.

    Returns:
        Texto con composición nutricional formateada y la fuente USDA.
    """
    results = await usda_search(food_query, max_results=3)
    return format_usda_results_for_llm(results)


@tool
async def search_health_news(query: str) -> str:
    """
    Busca información actualizada en internet sobre seguridad alimentaria,
    recalls de productos, evidencia científica reciente o tendencias dietéticas.

    Úsala cuando el usuario pregunte por:
    - Recalls o alertas sanitarias de productos específicos.
    - Noticias o reportes recientes (ej. "¿es seguro X?", "¿qué dicen los estudios
      nuevos sobre Y?").
    - Evidencia reciente sobre dietas (keto, ayuno intermitente, plant-based, etc).
    - Información que cambia con el tiempo (precios, disponibilidad, regulaciones).

    NO la uses para:
    - Composición nutricional de alimentos (usa get_nutrition_facts).
    - Diagnósticos médicos (recordá: NO somos médicos, derivar al profesional).

    Args:
        query: La consulta en lenguaje natural. Sé específico: "recall yogurt
               griego 2026 listeria" rinde mejor que "yogurt seguro".

    Returns:
        Hasta 4 resultados web con título, contenido y fuente.
    """
    results = await tavily_search_async(query, max_results=4)
    return format_tavily_results_for_llm(results)


# Lista exportada para el AgentExecutor
ALL_TOOLS = [get_nutrition_facts, search_health_news]
