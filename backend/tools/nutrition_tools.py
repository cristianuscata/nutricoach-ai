"""
Tools de información nutricional en tiempo real.

Estrategia de dos fuentes
-------------------------
1. USDA FoodData Central (primaria): autoridad pública, datos en CC0,
   gratis hasta 1000 req/h. Cubre composición nutricional exacta.
   - https://fdc.nal.usda.gov/api-guide

2. Tavily (secundaria): búsqueda web para lo que USDA no cubre — recalls,
   noticias, evidencia reciente, productos no incluidos en USDA.

El docstring de cada tool es lo que el LLM lee para decidir cuándo usarla.
Por eso son largos y específicos — no es ceremonia, es ingeniería de prompt.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from cachetools import TTLCache

from config import get_settings

logger = logging.getLogger(__name__)

# Cache en memoria: TTL=24h, hasta 512 queries únicas.
# Justificación: las composiciones nutricionales del USDA cambian raramente.
# Cachear nos protege del rate limit y reduce latencia de 400ms a <1ms.
_usda_cache: TTLCache[str, list[dict[str, Any]]] = TTLCache(maxsize=512, ttl=86400)


# --------------------------------------------------------------------------- #
# USDA FoodData Central                                                       #
# --------------------------------------------------------------------------- #

USDA_BASE = "https://api.nal.usda.gov/fdc/v1"

# Nutrientes que nos interesan (IDs del USDA).
# Ver https://fdc.nal.usda.gov/portal-data/external/nutrients
_NUTRIENT_IDS_OF_INTEREST = {
    1008: "Calorías (kcal)",
    1003: "Proteína (g)",
    1004: "Grasa total (g)",
    1005: "Carbohidratos (g)",
    1079: "Fibra (g)",
    2000: "Azúcares (g)",
    1093: "Sodio (mg)",
    1087: "Calcio (mg)",
    1089: "Hierro (mg)",
    1162: "Vitamina C (mg)",
    1178: "Vitamina B12 (µg)",
}


async def usda_search(query: str, max_results: int = 3) -> list[dict[str, Any]]:
    """
    Busca alimentos en la base USDA y devuelve composición nutricional formateada.

    Returns
    -------
    Lista de dicts con: name, brand, serving, nutrients (dict)
    """
    cache_key = f"{query.lower().strip()}::{max_results}"
    if cache_key in _usda_cache:
        logger.info("usda_cache_hit query=%r", query)
        return _usda_cache[cache_key]

    settings = get_settings()
    params = {
        "api_key": settings.usda_api_key,
        "query": query,
        "pageSize": max_results,
        # Priorizar Foundation y SR Legacy (datos más confiables) sobre Branded
        "dataType": ["Foundation", "SR Legacy", "Branded"],
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{USDA_BASE}/foods/search", params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            logger.warning("usda_api_error query=%r err=%s", query, e)
            return []

    foods = data.get("foods", [])[:max_results]
    results: list[dict[str, Any]] = []

    for food in foods:
        nutrients_map: dict[str, str] = {}
        for n in food.get("foodNutrients", []):
            nid = n.get("nutrientId")
            if nid in _NUTRIENT_IDS_OF_INTEREST:
                value = n.get("value")
                unit = n.get("unitName", "")
                if value is not None:
                    nutrients_map[_NUTRIENT_IDS_OF_INTEREST[nid]] = f"{value} {unit}"

        results.append({
            "name": food.get("description", "Sin nombre"),
            "brand": food.get("brandOwner") or food.get("brandName") or "Genérico",
            "serving": _format_serving(food),
            "nutrients": nutrients_map,
            "fdc_id": food.get("fdcId"),
            "source": "USDA FoodData Central",
        })

    _usda_cache[cache_key] = results
    return results


def _format_serving(food: dict[str, Any]) -> str:
    size = food.get("servingSize")
    unit = food.get("servingSizeUnit", "g")
    if size:
        return f"{size} {unit}"
    return "100 g (default)"


def format_usda_results_for_llm(results: list[dict[str, Any]]) -> str:
    """Convierte resultados USDA en texto markdown para que el LLM los cite."""
    if not results:
        return (
            "No se encontraron datos nutricionales en USDA para esa consulta. "
            "Considera reformular o usar la herramienta de búsqueda web."
        )

    blocks = []
    for r in results:
        nutrient_lines = "\n".join(f"  - {k}: {v}" for k, v in r["nutrients"].items())
        blocks.append(
            f"**{r['name']}** ({r['brand']})\n"
            f"Porción: {r['serving']}\n"
            f"{nutrient_lines}\n"
            f"Fuente: {r['source']} (FDC ID {r['fdc_id']})"
        )
    return "\n\n---\n\n".join(blocks)


# --------------------------------------------------------------------------- #
# Tavily (secundaria — para news, recalls, evidencia reciente)                #
# --------------------------------------------------------------------------- #

async def tavily_search_async(query: str, max_results: int = 4) -> list[dict[str, Any]]:
    """Búsqueda web vía Tavily. Solo se usa cuando USDA no aplica."""
    from tavily import AsyncTavilyClient

    settings = get_settings()
    client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    try:
        response = await client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_answer=False,
        )
    except Exception as e:
        logger.warning("tavily_error query=%r err=%s", query, e)
        return []

    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0.0),
        }
        for r in response.get("results", [])
    ]


def format_tavily_results_for_llm(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No se encontraron resultados en la búsqueda web."
    blocks = [
        f"**{r['title']}**\n{r['content']}\nFuente: {r['url']}"
        for r in results
    ]
    return "\n\n---\n\n".join(blocks)
