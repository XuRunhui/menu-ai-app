/**
 * TypeScript types matching the backend Pydantic models.
 */

export interface MenuItem {
  name: string;
  price: number;
  description: string | null;
}

export interface MenuCategory {
  category: string;
  items: MenuItem[];
}

export interface ParsedMenu {
  menu: MenuCategory[];
}
