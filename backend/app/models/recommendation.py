"""Pydantic models for the recommendation system API."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class BuildKnowledgeBaseRequest(BaseModel):
    """Request payload to build a restaurant knowledge base.

    Example:
        >>> BuildKnowledgeBaseRequest(
        ...     restaurant_name="Tartine Bakery",
        ...     location="San Francisco",
        ...     place_id="ChIJ...",
        ...     parsed_menu={"menu": []}
        ... )
    """

    restaurant_name: str = Field(..., description="Restaurant name", example="BCD Tofu House")
    location: str = Field(..., description="Restaurant location", example="Koreatown Los Angeles")
    place_id: Optional[str] = Field(
        None,
        description="Google Place ID for faster lookup",
        example="ChIJobNa..."
    )
    parsed_menu: Optional[Dict] = Field(
        None,
        description="Parsed menu data from OCR or external source"
    )

    class Config:
        schema_extra = {
            "example": {
                "restaurant_name": "Tartine Bakery",
                "location": "San Francisco",
                "place_id": "ChIJ...",
                "parsed_menu": {"menu": []}
            }
        }


class BuildKnowledgeBaseResponse(BaseModel):
    """Response payload for a knowledge base build request."""

    status: str = Field(..., description="Result status", example="success")
    total_documents: int = Field(..., description="Total documents indexed")
    menu_items: int = Field(..., description="Total menu items indexed")
    review_mentions: int = Field(..., description="Number of review mentions indexed")
    unique_dishes: int = Field(..., description="Unique dishes identified")
    sources: List[str] = Field(..., description="Data sources used")
    successful_sources: int = Field(..., description="Number of successful sources")
    failed_sources: List[Dict] = Field(default_factory=list, description="Failed sources with errors")
    build_time_seconds: float = Field(..., description="Time taken to build knowledge base")

    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "total_documents": 157,
                "menu_items": 24,
                "review_mentions": 128,
                "unique_dishes": 42,
                "sources": ["Google Places", "DuckDuckGo", "Yelp"],
                "successful_sources": 3,
                "failed_sources": [],
                "build_time_seconds": 9.72
            }
        }


class RecommendationRequest(BaseModel):
    """Request payload for dish recommendations."""

    restaurant_name: str = Field(..., description="Restaurant name")
    location: str = Field(..., description="Restaurant location")
    user_preferences: str = Field(..., description="User query", example="I want something spicy")
    top_k: int = Field(5, ge=1, le=20, description="Number of recommendations to return")
    use_llm_enhancement: bool = Field(True, description="Enhance explanations with LLM")
    filter_allergens: Optional[List[str]] = Field(
        None,
        description="Exclude dishes containing these allergens"
    )
    filter_dietary: Optional[List[str]] = Field(
        None,
        description="Only include dishes with these dietary tags"
    )

    class Config:
        schema_extra = {
            "example": {
                "restaurant_name": "BCD Tofu House",
                "location": "Koreatown LA",
                "user_preferences": "spicy Korean soup",
                "top_k": 5,
                "filter_allergens": ["nuts"],
                "filter_dietary": ["gluten-free"]
            }
        }


class DishRecommendation(BaseModel):
    """Single recommended dish with metadata and rationale."""

    dish_name: str = Field(..., description="Recommended dish name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    reasons: List[str] = Field(..., description="Top reasons for recommendation")
    review_count: int = Field(..., description="Number of review mentions")
    data_sources: List[str] = Field(..., description="Sources contributing to the recommendation")
    metadata: Dict = Field(default_factory=dict, description="Menu metadata and tags")
    taste_texture: Optional[Dict] = Field(None, description="Optional taste/texture prediction")

    class Config:
        schema_extra = {
            "example": {
                "dish_name": "Soon Tofu Jjigae",
                "confidence": 0.94,
                "reasons": [
                    "Mentioned in 12 reviews as must-try",
                    "Perfect match for spicy soup preference"
                ],
                "review_count": 12,
                "data_sources": ["Google Places", "DuckDuckGo"],
                "metadata": {"spicy_level": 3, "allergens": ["soy"]},
                "taste_texture": None
            }
        }


class RecommendationResponse(BaseModel):
    """Response payload for dish recommendations."""

    query: str = Field(..., description="User query that drove recommendations")
    recommendations: List[DishRecommendation] = Field(..., description="Ranked recommendations")
    total_dishes_analyzed: int = Field(..., description="Total dishes evaluated")
    search_time_seconds: float = Field(..., description="Search duration in seconds")

    class Config:
        schema_extra = {
            "example": {
                "query": "spicy Korean soup",
                "recommendations": [],
                "total_dishes_analyzed": 42,
                "search_time_seconds": 1.42
            }
        }


class TasteTextureRequest(BaseModel):
    """Request payload for taste/texture prediction."""

    dish_name: str = Field(..., description="Dish name")
    description: str = Field(..., description="Menu description for the dish")
    include_reviews: bool = Field(True, description="Whether to include review refinement")
    review_excerpts: Optional[List[str]] = Field(
        None,
        description="Optional review excerpts to use for round 2"
    )

    class Config:
        schema_extra = {
            "example": {
                "dish_name": "Soon Tofu Jjigae",
                "description": "Spicy soft tofu stew with seafood",
                "include_reviews": True
            }
        }


class TasteTextureResponse(BaseModel):
    """Response payload for taste/texture prediction."""

    dish_name: str = Field(..., description="Dish name")
    round1: Dict = Field(..., description="Round 1 prediction")
    round2: Optional[Dict] = Field(None, description="Round 2 prediction (if available)")
    improvement_score: Optional[float] = Field(
        None,
        description="Optional score reflecting round 2 improvement"
    )
    processing_time_seconds: float = Field(..., description="Total processing time")

    class Config:
        schema_extra = {
            "example": {
                "dish_name": "Soon Tofu Jjigae",
                "round1": {
                    "tastes": ["spicy", "umami"],
                    "textures": ["soft", "silky"],
                    "flavor_profile": "Rich and complex with moderate heat",
                    "confidence": 0.72,
                    "round": 1
                },
                "round2": None,
                "improvement_score": None,
                "processing_time_seconds": 1.1
            }
        }
