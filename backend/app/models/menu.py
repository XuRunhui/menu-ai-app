"""Menu data models matching the Gemini vision parser output format."""

from pydantic import BaseModel, Field


class MenuItem(BaseModel):
    """A single menu item with name, price, description, and dietary information.

    Example:
        >>> item = MenuItem(
        ...     name="Spicy Tonkatsu Ramen",
        ...     price=14.99,
        ...     description="Pork cutlet with spicy miso broth",
        ...     spicy_level=3,
        ...     allergens=["gluten", "soy", "eggs"],
        ...     dietary_tags=[]
        ... )
        >>> item.spicy_level
        3
        >>> "gluten" in item.allergens
        True
    """

    name: str = Field(..., description="The name of the dish")
    name_translated: str | None = Field(None, description="Translated dish name")
    price: float | None = Field(None, description="The numeric price of the dish")
    price_original: str | None = Field(None, description="Original price text (e.g., '八百円', '十块')")
    currency: str | None = Field(None, description="Currency symbol or code (e.g., '$', '¥', 'USD')")
    description: str | None = Field(None, description="Optional description or ingredients")
    description_translated: str | None = Field(None, description="Translated description")

    # NEW: Dietary and symbol detection fields
    spicy_level: int | None = Field(
        None,
        ge=0,
        le=5,
        description="Spiciness level from 0-5 (🌶️ symbols or * asterisks)"
    )
    allergens: list[str] = Field(
        default_factory=list,
        description="List of allergens (e.g., ['nuts', 'dairy', 'gluten', 'shellfish'])"
    )
    dietary_tags: list[str] = Field(
        default_factory=list,
        description="Dietary classifications (e.g., ['vegetarian', 'vegan', 'gluten-free'])"
    )


class MenuCategory(BaseModel):
    """A category of menu items (e.g., Appetizers, Entrees)."""

    category: str = Field(..., description="The category name")
    category_translated: str | None = Field(None, description="Translated category name")
    items: list[MenuItem] = Field(default_factory=list, description="List of items in this category")


class ParsedMenu(BaseModel):
    """Complete parsed menu structure from vision parsing."""

    detected_language: str | None = Field(None, description="Detected language of the menu")
    target_language: str | None = Field(None, description="Target language for translation")
    menu: list[MenuCategory] = Field(default_factory=list, description="List of menu categories")
