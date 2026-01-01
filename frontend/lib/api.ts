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
