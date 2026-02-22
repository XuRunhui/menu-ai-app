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

export interface DishContextResponse {
  dish_name: string;
  menu_description: string | null;
  dish_image_url?: string | null;
  review_count: number;
  review_excerpts: string[];
  metadata: {
    price?: number | null;
    spicy_level?: number | null;
    allergens?: string[];
    dietary_tags?: string[];
    category?: string | null;
  };
  is_popular: boolean;
  popularity_score: number;
  taste_texture?: {
    round1?: {
      tastes: string[];
      textures: string[];
      flavor_profile: string;
      confidence: number;
    };
    round2?: {
      tastes: string[];
      textures: string[];
      flavor_profile: string;
      confidence: number;
      changes_from_round1?: string[];
    };
    improvement_score?: number;
  };
}
