"""Knowledge base endpoints: stats, passage search, and dish combo recommendations."""

import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.rate_limit import enforce_demo_limits, llm_budget_exhausted
from app.knowledge.combos import DishInput, recommend_combos_with_context
from app.knowledge.db import knowledge_session
from app.knowledge.retrieval import search_passages
from app.knowledge.store import stats
from app.models.knowledge import ComboRequest, ComboResponse, PassageHit
from app.services import cache_service

# Bump when the combo pipeline changes enough that cached responses should be recomputed.
COMBO_CACHE_VERSION = "2"  # 2: each ingredient pairing listed once

router = APIRouter()


def _knowledge_ready(db) -> bool:
    """Whether the pairing graph has been built (combos still work without it, with less evidence)."""
    counts = stats(db)
    return bool(counts["edges"].get("pairs_with"))


@router.get("/stats")
def knowledge_stats() -> dict:
    with knowledge_session() as db:
        return stats(db)


@router.get("/search", response_model=list[PassageHit], dependencies=[Depends(enforce_demo_limits)])
def search(q: str = Query(..., min_length=2, max_length=500), top_k: int = Query(5, ge=1, le=20)):
    with knowledge_session() as db:
        return search_passages(db, q, top_k=top_k)


def combo_cache_key(request: ComboRequest) -> str:
    """Same menu + options -> same key, so a finished combo response is reused for everyone."""
    payload = {
        "dishes": [dish.model_dump() for dish in request.dishes],
        "max_combos": request.max_combos,
        "restaurant": request.restaurant_name or "",
        "model": settings.deepseek_model,
        "version": COMBO_CACHE_VERSION,
    }
    return cache_service.sha256_hex("combo_response", json.dumps(payload, sort_keys=True, ensure_ascii=False))


def _cached_combos(request: ComboRequest) -> ComboResponse | None:
    cached = cache_service.get_llm_response(combo_cache_key(request))
    return ComboResponse.model_validate_json(cached) if cached else None


def _combos(request: ComboRequest) -> ComboResponse:
    cached = _cached_combos(request)
    if cached is not None:
        return cached

    response = compute_combos(request)
    # Only cache model-written combos: keyword-fallback results (no key yet, or the demo's AI budget
    # spent for now) should be worked out properly next time.
    if response.combos and settings.deepseek_api_key and not llm_budget_exhausted():
        cache_service.set_llm_response(combo_cache_key(request), settings.deepseek_model, "combo_response",
                                       response.model_dump_json())
    return response


def compute_combos(request: ComboRequest) -> ComboResponse:
    llm_client = None
    if settings.deepseek_api_key:
        from app.services.llm_client import LLMClient

        llm_client = LLMClient(api_key=settings.deepseek_api_key)

    with knowledge_session() as db:
        dishes = [DishInput(d.name, d.description or "", d.category or "") for d in request.dishes]
        result = recommend_combos_with_context(
            db, dishes, request.max_combos, llm_client, restaurant=request.restaurant_name or ""
        )
        return ComboResponse(**result, knowledge_available=_knowledge_ready(db))


@router.post("/combos", response_model=ComboResponse)
async def combos(request: ComboRequest, http_request: Request) -> ComboResponse:
    """Suggest dish combos from a menu: profiled and chosen by DeepSeek, grounded in meal-composition rules,
    cultural meal structures, and FlavorGraph ingredient pairings.

    Combos already worked out (the sample menu's are seeded) are free; only new work counts
    toward the demo limits."""
    cached = await run_in_threadpool(_cached_combos, request)
    if cached is not None:
        return cached
    await enforce_demo_limits(http_request)
    return await run_in_threadpool(_combos, request)
