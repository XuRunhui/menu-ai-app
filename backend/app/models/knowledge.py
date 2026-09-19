"""Request/response models for knowledge endpoints."""

from pydantic import BaseModel, Field


class ComboDish(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    category: str | None = Field(None, max_length=255)


class ComboRequest(BaseModel):
    dishes: list[ComboDish] = Field(..., min_length=2, max_length=200)
    max_combos: int = Field(3, ge=1, le=6)
    restaurant_name: str | None = Field(None, max_length=255)


class ComboPairing(BaseModel):
    a: str
    b: str
    weight: float
    source: str


class ComboSource(BaseModel):
    title: str
    url: str
    license: str
    excerpt: str
    page: int | None = None


class DishTraitsSummary(BaseModel):
    name: str
    role: str
    tastes: list[str]
    textures: list[str]
    colors: list[str]
    temperature: str
    weight: str


class Combo(BaseModel):
    dishes: list[str]
    score: float
    title: str
    explanation: str
    cultural_note: str = ""
    tip: str
    reasons: list[str] = []
    dish_profiles: list[DishTraitsSummary] = []
    pairings: list[ComboPairing]
    shared_compounds: list[str]
    sources: list[ComboSource]


class ComboResponse(BaseModel):
    combos: list[Combo]
    cuisine: str = ""
    knowledge_available: bool
    attribution: str = (
        "Ingredient pairings: FlavorGraph (Apache-2.0). Dish data: Wikidata (CC0). "
        "Meal customs: Wikipedia (CC BY-SA 4.0) and Menuist notes."
    )


class PassageHit(BaseModel):
    chunk_id: int
    score: float
    text: str
    page: int | None
    document_title: str
    url: str
    license: str
