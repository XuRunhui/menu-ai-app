"""Recommendation API endpoints for RAG-based dish suggestions."""

from typing import Dict, List, Optional
import logging
import time

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.config import settings
from app.models.recommendation import (
    BuildKnowledgeBaseRequest,
    BuildKnowledgeBaseResponse,
    RecommendationRequest,
    RecommendationResponse,
    TasteTextureRequest,
    TasteTextureResponse,
)
from app.services.recommendation.rag_engine import RAGRecommendationEngine
from app.services.recommendation.taste_texture_predictor import TasteTexturePredictor
from app.services.dish_image_service import get_dish_image_service

router = APIRouter()
logger = logging.getLogger(__name__)

_ENGINE_CACHE: Dict[str, RAGRecommendationEngine] = {}
_LAST_ENGINE_KEY: Optional[str] = None


def _cache_key(restaurant_name: str, location: str) -> str:
    return f"{restaurant_name.strip().lower()}::{location.strip().lower()}"


def _get_engine(restaurant_name: str, location: str) -> RAGRecommendationEngine:
    global _LAST_ENGINE_KEY
    key = _cache_key(restaurant_name, location)
    engine = _ENGINE_CACHE.get(key)
    if not engine:
        engine = RAGRecommendationEngine(
            gemini_api_key=settings.gemini_api_key,
            google_places_api_key=settings.google_places_api_key,
            yelp_api_key=settings.yelp_api_key,
            model_name=settings.gemini_model,
            cache_enabled=settings.rag_cache_enabled,
            cache_ttl_seconds=settings.rag_cache_ttl_seconds
        )
        _ENGINE_CACHE[key] = engine
    _LAST_ENGINE_KEY = key
    return engine


def _get_last_engine() -> Optional[RAGRecommendationEngine]:
    if _LAST_ENGINE_KEY and _LAST_ENGINE_KEY in _ENGINE_CACHE:
        return _ENGINE_CACHE[_LAST_ENGINE_KEY]
    return None


def _filter_recommendations(
    recommendations: List[Dict],
    filter_allergens: Optional[List[str]],
    filter_dietary: Optional[List[str]]
) -> List[Dict]:
    if not filter_allergens and not filter_dietary:
        return recommendations

    allergen_set = {item.lower() for item in (filter_allergens or [])}
    dietary_set = {item.lower() for item in (filter_dietary or [])}

    filtered = []
    for rec in recommendations:
        metadata = rec.get("metadata", {})
        allergens = {item.lower() for item in metadata.get("allergens", [])}
        dietary_tags = {item.lower() for item in metadata.get("dietary_tags", [])}

        if allergen_set and allergens.intersection(allergen_set):
            continue
        if dietary_set and not dietary_set.issubset(dietary_tags):
            continue

        filtered.append(rec)

    return filtered


def _calc_improvement(round1: Dict, round2: Dict) -> Optional[float]:
    if not round1 or not round2:
        return None
    try:
        return round(round2.get("confidence", 0.0) - round1.get("confidence", 0.0), 3)
    except (TypeError, ValueError):
        return None


@router.post("/build-knowledge-base", response_model=BuildKnowledgeBaseResponse)
async def build_knowledge_base(request: BuildKnowledgeBaseRequest):
    """Build or rebuild a knowledge base for a restaurant."""
    if not request.restaurant_name.strip() or not request.location.strip():
        raise HTTPException(status_code=400, detail="restaurant_name and location are required")

    if not settings.gemini_api_key:
        msg = "GEMINI_API_KEY environment variable not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    logger.info(f"[build-knowledge-base] Start - restaurant: {request.restaurant_name}")
    start_time = time.perf_counter()

    try:
        engine = _get_engine(request.restaurant_name, request.location)
        stats = await engine.build_knowledge_base(
            restaurant_name=request.restaurant_name,
            location=request.location,
            place_id=request.place_id,
            parsed_menu=request.parsed_menu
        )
    except Exception as e:
        msg = f"Knowledge base build failed: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg) from e

    if stats.get("successful_sources", 0) == 0 and stats.get("total_documents", 0) == 0:
        msg = "Collection failed from all sources"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    elapsed = round(time.perf_counter() - start_time, 3)
    logger.info(
        f"[build-knowledge-base] Completed - restaurant: {request.restaurant_name}, "
        f"user: unknown, duration: {elapsed}s"
    )

    return BuildKnowledgeBaseResponse(
        status="success",
        total_documents=stats.get("total_documents", 0),
        menu_items=stats.get("menu_items", 0),
        review_mentions=stats.get("review_mentions", 0),
        unique_dishes=stats.get("unique_dishes", 0),
        sources=stats.get("sources", []),
        successful_sources=stats.get("successful_sources", 0),
        failed_sources=stats.get("failed_sources", []),
        build_time_seconds=elapsed
    )


@router.post("/recommend", response_model=RecommendationResponse)
async def recommend_dishes(
    request: RecommendationRequest,
    include_taste_texture: bool = Query(False, description="Add taste/texture predictions")
):
    """Get dish recommendations based on user preferences."""
    if not request.restaurant_name.strip() or not request.location.strip():
        raise HTTPException(status_code=400, detail="restaurant_name and location are required")
    if not request.user_preferences.strip():
        raise HTTPException(status_code=400, detail="user_preferences is required")

    if request.use_llm_enhancement and not settings.gemini_api_key:
        msg = "GEMINI_API_KEY environment variable not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    if include_taste_texture and not settings.gemini_api_key:
        msg = "GEMINI_API_KEY environment variable not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    logger.info(f"[recommend] Start - restaurant: {request.restaurant_name}")
    start_time = time.perf_counter()

    try:
        engine = _get_engine(request.restaurant_name, request.location)
        if not engine.knowledge_base_built:
            await engine.build_knowledge_base(
                restaurant_name=request.restaurant_name,
                location=request.location
            )

        recommendations = engine.recommend_dishes(
            user_preferences=request.user_preferences,
            top_k=request.top_k,
            use_llm=request.use_llm_enhancement
        )
    except ValueError as e:
        msg = str(e)
        logger.error(msg)
        raise HTTPException(status_code=404, detail=msg) from e
    except Exception as e:
        msg = f"Recommendation generation failed: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg) from e

    recommendations = _filter_recommendations(
        recommendations,
        request.filter_allergens,
        request.filter_dietary
    )

    if include_taste_texture and recommendations:
        predictor = TasteTexturePredictor(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_model
        )
        for rec in recommendations:
            context = engine.get_dish_context(rec["dish_name"]) or {}
            description = context.get("menu_description", "")
            reviews = context.get("review_excerpts", [])
            if not description:
                rec["taste_texture"] = None
                continue
            round1 = await predictor.predict_round1(rec["dish_name"], description)
            round2 = None
            improvement = None
            if reviews:
                round2 = await predictor.predict_round2(
                    rec["dish_name"],
                    description,
                    reviews,
                    round1
                )
                improvement = _calc_improvement(round1, round2)
            rec["taste_texture"] = {
                "round1": round1,
                "round2": round2,
                "improvement_score": improvement
            }

    elapsed = round(time.perf_counter() - start_time, 3)
    logger.info(
        f"[recommend] Completed - restaurant: {request.restaurant_name}, "
        f"user: unknown, duration: {elapsed}s"
    )

    total_dishes = len(getattr(engine, "dish_names", []))
    total_dishes = max(total_dishes, len(recommendations))

    return RecommendationResponse(
        query=request.user_preferences,
        recommendations=recommendations,
        total_dishes_analyzed=total_dishes,
        search_time_seconds=elapsed
    )


@router.post("/taste-texture", response_model=TasteTextureResponse)
async def taste_texture(request: TasteTextureRequest):
    """Predict taste and texture for a dish."""
    if not request.dish_name.strip() or not request.description.strip():
        raise HTTPException(status_code=400, detail="dish_name and description are required")

    if not settings.gemini_api_key:
        msg = "GEMINI_API_KEY environment variable not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    logger.info(f"[taste-texture] Start - dish: {request.dish_name}")
    start_time = time.perf_counter()

    predictor = TasteTexturePredictor(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model
    )

    round1 = await predictor.predict_round1(request.dish_name, request.description)
    round2 = None
    improvement = None

    if request.include_reviews:
        review_excerpts = request.review_excerpts or []
        if not review_excerpts:
            engine = _get_last_engine()
            if engine:
                context = engine.get_dish_context(request.dish_name) or {}
                review_excerpts = context.get("review_excerpts", [])
        if review_excerpts:
            round2 = await predictor.predict_round2(
                request.dish_name,
                request.description,
                review_excerpts,
                round1
            )
            improvement = _calc_improvement(round1, round2)

    elapsed = round(time.perf_counter() - start_time, 3)
    logger.info(
        f"[taste-texture] Completed - dish: {request.dish_name}, "
        f"user: unknown, duration: {elapsed}s"
    )

    return TasteTextureResponse(
        dish_name=request.dish_name,
        round1=round1,
        round2=round2,
        improvement_score=improvement,
        processing_time_seconds=elapsed
    )


@router.get("/dish/{dish_name}")
async def get_dish_context(
    request: Request,
    dish_name: str,
    restaurant_name: str = Query(..., description="Restaurant name"),
    location: str = Query(..., description="Restaurant location")
):
    """Get all available context about a specific dish."""
    if not restaurant_name.strip() or not location.strip():
        raise HTTPException(status_code=400, detail="restaurant_name and location are required")

    logger.info(f"[dish-context] Start - dish: {dish_name}, restaurant: {restaurant_name}")
    start_time = time.perf_counter()

    try:
        engine = _get_engine(restaurant_name, location)
        if not engine.knowledge_base_built:
            await engine.build_knowledge_base(
                restaurant_name=restaurant_name,
                location=location
            )
    except Exception as e:
        msg = f"Failed to build knowledge base: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg) from e

    context = engine.get_dish_context(dish_name)
    if not context:
        raise HTTPException(status_code=404, detail="Dish not found in knowledge base")

    taste_texture = None
    if settings.gemini_api_key and context.get("menu_description"):
        predictor = TasteTexturePredictor(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_model
        )
        round1 = await predictor.predict_round1(dish_name, context["menu_description"])
        round2 = None
        improvement = None
        if context.get("review_excerpts"):
            round2 = await predictor.predict_round2(
                dish_name,
                context["menu_description"],
                context["review_excerpts"],
                round1
            )
            improvement = _calc_improvement(round1, round2)
        taste_texture = {
            "round1": round1,
            "round2": round2,
            "improvement_score": improvement
        }

    context["taste_texture"] = taste_texture

    # Attach cached dish image URL (check only — do not trigger a new fetch here)
    image_service = get_dish_image_service()
    cached_filename = image_service.get_cached_filename(restaurant_name, dish_name)
    if cached_filename:
        base_url = str(request.base_url).rstrip("/")
        context["dish_image_url"] = f"{base_url}/dish-images/{cached_filename}"
    else:
        context["dish_image_url"] = None

    elapsed = round(time.perf_counter() - start_time, 3)
    logger.info(
        f"[dish-context] Completed - dish: {dish_name}, "
        f"user: unknown, duration: {elapsed}s"
    )

    return context
