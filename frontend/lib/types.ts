/**
 * TypeScript types matching the backend Pydantic models.
 */

/** Where a dish was found when a menu is combined from several places. */
export type MenuSourceKind = 'website' | 'upload' | 'reviews';

/** A different price for the same dish in another source — often a sign one is out of date. */
export interface AltPrice {
  source: MenuSourceKind;
  price: number | null;
  price_original?: string | null;
  currency?: string | null;
}

export interface MenuItem {
  name: string;
  name_translated?: string | null;
  price: number | null;
  price_original?: string | null;
  currency?: string | null;
  description: string | null;
  description_translated?: string | null;
  /** Filled in for combined menus; empty for a menu read from one photo. */
  sources?: MenuSourceKind[];
  alt_prices?: AltPrice[];
  review_mentions?: number | null;
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
  /** Shared cache id; /results?menu=<id> restores this menu after a refresh. */
  menu_id?: string | null;
}

export interface MenuRecord {
  menu_id: string;
  restaurant_name: string;
  target_language: string;
  detected_language: string | null;
  item_count: number;
  parsed_menu: ParsedMenu;
}

export interface SavedMenuSummary {
  id: number;
  menu_id: string | null;
  restaurant_name: string;
  target_language: string;
  detected_language: string | null;
  item_count: number;
  created_at: string;
  updated_at: string;
}

export interface SavedMenuDetail extends SavedMenuSummary {
  parsed_menu: ParsedMenu;
}

export interface RestaurantHistoryItem {
  place_id: string;
  label: string;
  viewed_at: string;
}

export interface ComboPairing {
  a: string;
  b: string;
  weight: number;
  source: string;
}

export interface ComboSource {
  title: string;
  url: string;
  license: string;
  excerpt: string;
  page: number | null;
}

export interface DishTraitsSummary {
  name: string;
  role: string;
  tastes: string[];
  textures: string[];
  colors: string[];
  temperature: string;
  weight: string;
}

export interface Combo {
  dishes: string[];
  score: number;
  title: string;
  explanation: string;
  cultural_note: string;
  tip: string;
  reasons: string[];
  dish_profiles: DishTraitsSummary[];
  pairings: ComboPairing[];
  shared_compounds: string[];
  sources: ComboSource[];
}

export interface ComboResponse {
  combos: Combo[];
  cuisine: string;
  knowledge_available: boolean;
  attribution: string;
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
