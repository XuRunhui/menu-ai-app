/**
 * TypeScript types matching the backend Pydantic models.
 */

export interface MenuItem {
  name: string;
  name_translated?: string | null;
  price: number | null;
  price_original?: string | null;
  currency?: string | null;
  description: string | null;
  description_translated?: string | null;
}

export interface MenuCategory {
  category: string;
  category_translated?: string | null;
  items: MenuItem[];
}

export interface ParsedMenu {
  detected_language?: string | null;
  target_language?: string | null;
  menu: MenuCategory[];
}
