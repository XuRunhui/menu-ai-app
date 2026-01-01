"""Restaurant data models for Yelp API integration."""

from pydantic import BaseModel, Field
from datetime import datetime


class YelpCoordinates(BaseModel):
    """Geographic coordinates."""

    latitude: float
    longitude: float


class YelpLocation(BaseModel):
    """Business location information."""

    address1: str | None = None
    address2: str | None = None
    address3: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None
    display_address: list[str] = Field(default_factory=list)


class YelpCategory(BaseModel):
    """Business category."""

    alias: str
    title: str


class YelpBusiness(BaseModel):
    """Yelp business information."""

    id: str
    name: str
    image_url: str | None = None
    url: str
    rating: float
    review_count: int
    price: str | None = None  # "$", "$$", "$$$", "$$$$"
    categories: list[YelpCategory] = Field(default_factory=list)
    location: YelpLocation
    coordinates: YelpCoordinates | None = None
    phone: str | None = None
    display_phone: str | None = None
    photos: list[str] = Field(default_factory=list, description="Additional business photos")


class YelpUser(BaseModel):
    """Yelp review user information."""

    name: str
    image_url: str | None = None


class YelpReview(BaseModel):
    """Yelp review data."""

    id: str
    url: str
    text: str
    rating: int
    time_created: str
    user: YelpUser


class PopularDish(BaseModel):
    """Popular dish extracted from reviews."""

    name: str = Field(..., description="Dish name")
    mention_count: int = Field(..., description="Number of times mentioned in reviews")
    avg_sentiment: float = Field(default=0.8, description="Average sentiment score (0-1)")
    sample_reviews: list[str] = Field(default_factory=list, description="Sample review excerpts")


class RestaurantData(BaseModel):
    """Complete restaurant data with reviews and popular dishes."""

    business: YelpBusiness
    reviews: list[YelpReview] = Field(default_factory=list)
    popular_dishes: list[PopularDish] = Field(default_factory=list)
    cached_at: datetime | None = None


class RestaurantSearchRequest(BaseModel):
    """Request model for restaurant search."""

    name: str = Field(..., description="Restaurant name to search for")
    location: str = Field(..., description="Location (city, state or zip code)")


class RestaurantSearchResponse(BaseModel):
    """Response model for restaurant search."""

    businesses: list[YelpBusiness]
    total: int = Field(default=0, description="Total number of results")
