// ─── Menu ────────────────────────────────────────────────────────────────────

export interface MenuItem {
  name: string;
  name_translated?: string | null;
  price: number | null;
  price_original?: string | null;
  currency?: string | null;
  description: string | null;
  description_translated?: string | null;
  spicy_level?: number | null;
  allergens?: string[];
  dietary_tags?: string[];
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

// ─── Places ──────────────────────────────────────────────────────────────────

export interface GooglePlace {
  place_id: string;
  name: string;
  formatted_address?: string;
  rating?: number;
  user_ratings_total?: number;
  photo_urls?: string[];
}

export interface PopularDish {
  name: string;
  mention_count: number;
  sentiment_score: number;
  sample_reviews?: string[];
}

export interface PlaceDetailsResponse {
  place: {
    place_id: string;
    name: string;
    formatted_address?: string;
    rating?: number;
    user_ratings_total?: number;
    price_level?: number;
    photo_urls?: string[];
    website?: string;
    formatted_phone_number?: string;
  };
  popular_dishes?: PopularDish[];
}

export interface PlaceSearchResponse {
  results: GooglePlace[];
  status: string;
}

// ─── Recommendations ─────────────────────────────────────────────────────────

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

export interface DishImageResponse {
  image_url: string | null;
  cached: boolean;
}

// ─── App State ───────────────────────────────────────────────────────────────

export interface RestaurantInfo {
  place_id: string;
  name: string;
  location: string;
  rating?: number;
  photo_urls?: string[];
}
