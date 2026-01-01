"""Data models for Google Places API responses."""

from pydantic import BaseModel, Field
from typing import Optional


class GooglePlaceGeometry(BaseModel):
    """Location geometry for a Google Place."""
    lat: float
    lng: float


class GooglePlacePhoto(BaseModel):
    """Photo reference for a Google Place."""
    photo_reference: str
    width: int
    height: int


class GooglePlace(BaseModel):
    """Basic Google Place information from search."""
    place_id: str
    name: str
    formatted_address: str
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    price_level: Optional[int] = None  # 0-4 scale
    types: list[str] = Field(default_factory=list)
    geometry: Optional[dict] = None
    photos: list[dict] = Field(default_factory=list)
    business_status: Optional[str] = None


class GooglePlaceReview(BaseModel):
    """Review for a Google Place."""
    author_name: str
    author_url: Optional[str] = None
    language: Optional[str] = None
    profile_photo_url: Optional[str] = None
    rating: int
    relative_time_description: str
    text: str
    time: int  # Unix timestamp


class GooglePlaceDetails(BaseModel):
    """Detailed Google Place information."""
    place_id: str
    name: str
    formatted_address: str
    formatted_phone_number: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    price_level: Optional[int] = None
    types: list[str] = Field(default_factory=list)
    geometry: Optional[dict] = None
    opening_hours: Optional[dict] = None
    photos: list[dict] = Field(default_factory=list)
    photo_urls: list[str] = Field(default_factory=list)
    reviews: list[GooglePlaceReview] = Field(default_factory=list)


class PlaceSearchRequest(BaseModel):
    """Request model for place search."""
    query: str
    location: Optional[str] = None


class PlaceSearchResponse(BaseModel):
    """Response model for place search."""
    results: list[GooglePlace]
    status: str


class PlaceData(BaseModel):
    """Complete place data including reviews and popular dishes."""
    place: GooglePlaceDetails
    reviews: list[GooglePlaceReview]
    popular_dishes: list[dict] = Field(default_factory=list)
    cached_at: Optional[str] = None
