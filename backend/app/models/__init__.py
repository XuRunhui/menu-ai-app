"""Data models for the Menu AI application."""

from app.models.menu import MenuItem, MenuCategory, ParsedMenu
from app.models.recommendation import (
    BuildKnowledgeBaseRequest,
    BuildKnowledgeBaseResponse,
    RecommendationRequest,
    DishRecommendation,
    RecommendationResponse,
    TasteTextureRequest,
    TasteTextureResponse
)

__all__ = [
    "MenuItem",
    "MenuCategory",
    "ParsedMenu",
    "BuildKnowledgeBaseRequest",
    "BuildKnowledgeBaseResponse",
    "RecommendationRequest",
    "DishRecommendation",
    "RecommendationResponse",
    "TasteTextureRequest",
    "TasteTextureResponse"
]
