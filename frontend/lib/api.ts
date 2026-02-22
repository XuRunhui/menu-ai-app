/**
 * API client for the Menu AI backend.
 */

import { ParsedMenu } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Google Places API types
export interface GooglePlace {
  place_id: string;
  name: string;
  formatted_address: string;
  rating?: number;
  user_ratings_total?: number;
  price_level?: number;
  types?: string[];
  geometry?: {
    location: {
      lat: number;
      lng: number;
    };
  };
  photos?: Array<{
    photo_reference: string;
    width: number;
    height: number;
  }>;
  business_status?: string;
}

export interface PlaceSearchResponse {
  results: GooglePlace[];
  status: string;
}

export interface GooglePlaceReview {
  author_name: string;
  author_url?: string;
  language?: string;
  profile_photo_url?: string;
  rating: number;
  relative_time_description: string;
  text: string;
  time: number;
}

export interface PopularDish {
  name: string;
  mention_count: number;
  avg_sentiment: number;
  sample_reviews: string[];
}

export interface PlaceDetailsResponse {
  place: GooglePlace & {
    formatted_phone_number?: string;
    website?: string;
    opening_hours?: any;
    photo_urls?: string[];
    reviews?: GooglePlaceReview[];
  };
  reviews: GooglePlaceReview[];
  popular_dishes: PopularDish[];
  cached_at?: string | null;
}

/**
 * Parse a menu image using the backend API with optional translation.
 *
 * @param imageFile - The image file to parse
 * @param targetLanguage - Optional target language for translation (e.g., "English", "Chinese", "Japanese")
 * @returns Parsed menu structure with categories and items in original and optionally translated languages
 * @throws Error if the API request fails
 */
export async function parseMenu(
  imageFile: File,
  targetLanguage?: string | null
): Promise<ParsedMenu> {
  const formData = new FormData();
  formData.append('image', imageFile);

  if (targetLanguage) {
    formData.append('target_language', targetLanguage);
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/menu/parse`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error ${response.status}`);
  }

  return response.json();
}

/**
 * Search for places using Google Places API.
 *
 * @param query - Search query (e.g., "tofu house koreatown" or "Tartine Bakery San Francisco")
 * @returns List of matching places
 * @throws Error if the API request fails
 */
export async function searchPlaces(query: string): Promise<PlaceSearchResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/places/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error ${response.status}`);
  }

  return response.json();
}

/**
 * Get detailed place information including reviews and popular dishes.
 *
 * @param placeId - Google Place ID
 * @returns Place details with reviews and popular dishes
 * @throws Error if the API request fails
 */
export async function getPlaceDetails(placeId: string): Promise<PlaceDetailsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/places/${placeId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error ${response.status}`);
  }

  return response.json();
}

export interface BuildKnowledgeBaseRequest {
  restaurant_name: string;
  location: string;
  place_id?: string;
}

export interface BuildKnowledgeBaseResponse {
  status: string;
  total_documents: number;
  menu_items?: number;
  review_mentions?: number;
  unique_dishes?: number;
  sources?: string[];
  build_time_seconds?: number;
}

/**
 * Build the RAG knowledge base for a restaurant.
 * This is typically fired in the background after place selection.
 *
 * @param req - Restaurant name, location, and optional place_id
 * @returns Knowledge base build status
 * @throws Error if the API request fails
 */
export async function buildKnowledgeBase(req: BuildKnowledgeBaseRequest): Promise<BuildKnowledgeBaseResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/recommendation/build-knowledge-base`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error ${response.status}`);
  }

  return response.json();
}

/**
 * Get LLM-generated context for a specific dish, including flavor predictions
 * and curated review excerpts.
 *
 * @param dishName - The dish name to look up
 * @param restaurantName - Restaurant name (required by the backend)
 * @param location - Restaurant location/address (required by the backend)
 * @returns Dish context with description, review excerpts, and taste/texture data
 * @throws Error if the API request fails
 */
export async function getDishContext(
  dishName: string,
  restaurantName: string,
  location: string
): Promise<import('./types').DishContextResponse> {
  const params = new URLSearchParams({
    restaurant_name: restaurantName,
    location,
  });

  const response = await fetch(
    `${API_BASE_URL}/api/v1/recommendation/dish/${encodeURIComponent(dishName)}?${params}`
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error ${response.status}`);
  }

  return response.json();
}

export interface DishImageResponse {
  image_url: string | null;
  cached: boolean;
}

/**
 * Fetch (and cache) a dish image via DuckDuckGo image search.
 * On first call for a dish the backend performs the web search, downloads
 * the image, and stores it locally. Subsequent calls are served from cache.
 *
 * @param dishName - Name of the dish
 * @param restaurantName - Restaurant name used to scope the image search
 * @returns Image URL pointing to the locally-cached file, or null if not found
 */
export async function getDishImage(
  dishName: string,
  restaurantName?: string
): Promise<DishImageResponse> {
  const params = new URLSearchParams({ dish_name: dishName });
  if (restaurantName) params.set('restaurant_name', restaurantName);

  const response = await fetch(`${API_BASE_URL}/api/v1/dish-image?${params}`);

  if (!response.ok) {
    return { image_url: null, cached: false };
  }

  return response.json();
}
