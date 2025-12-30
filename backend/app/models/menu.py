"""Menu data models matching the Gemini vision parser output format."""

from pydantic import BaseModel, Field


class MenuItem(BaseModel):
    """A single menu item with name, price, and description."""

    name: str = Field(..., description="The name of the dish")
    price: float = Field(..., description="The price of the dish")
    description: str | None = Field(None, description="Optional description or ingredients")


class MenuCategory(BaseModel):
    """A category of menu items (e.g., Appetizers, Entrees)."""

    category: str = Field(..., description="The category name")
    items: list[MenuItem] = Field(default_factory=list, description="List of items in this category")


class ParsedMenu(BaseModel):
    """Complete parsed menu structure from vision parsing."""

    menu: list[MenuCategory] = Field(default_factory=list, description="List of menu categories")
