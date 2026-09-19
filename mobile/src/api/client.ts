/**
 * API client — all network calls to the Menuist backend.
 * Pure functions, no React hooks, no side effects.
 * Maps 1:1 to backend endpoints for easy SwiftUI rewrite.
 */

import {
  ParsedMenu,
  PlaceSearchResponse,
  PlaceDetailsResponse,
  DishContextResponse,
  DishImageResponse,
} from '@/types';

const API_BASE =
  (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ─── Menu Parsing ─────────────────────────────────────────────────────────────

/**
 * POST /api/v1/menu/parse
 * Uploads a menu image and returns the parsed menu structure.
 * @param imageUri  Local file URI from expo-image-picker
 * @param targetLanguage  Optional translation target (e.g. "Chinese")
 */
export async function parseMenu(
  imageUri: string,
  targetLanguage?: string | null,
): Promise<ParsedMenu> {
  const fd = new FormData();
  // React Native FormData accepts { uri, name, type } objects
  fd.append('image', { uri: imageUri, name: 'menu.jpg', type: 'image/jpeg' } as unknown as Blob);
  if (targetLanguage) fd.append('target_language', targetLanguage);

  const res = await fetch(`${API_BASE}/api/v1/menu/parse`, {
    method: 'POST',
    body: fd,
    // Do NOT set Content-Type manually — fetch sets boundary automatically for FormData
  });
  return handleResponse<ParsedMenu>(res);
}

// ─── Google Places ────────────────────────────────────────────────────────────

/**
 * POST /api/v1/places/search
 */
export async function searchPlaces(query: string): Promise<PlaceSearchResponse> {
  const res = await fetch(`${API_BASE}/api/v1/places/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  return handleResponse<PlaceSearchResponse>(res);
}

/**
 * GET /api/v1/places/{place_id}
 */
export async function getPlaceDetails(placeId: string): Promise<PlaceDetailsResponse> {
  const res = await fetch(`${API_BASE}/api/v1/places/${encodeURIComponent(placeId)}`);
  return handleResponse<PlaceDetailsResponse>(res);
}

// ─── RAG / Recommendations ───────────────────────────────────────────────────

/**
 * POST /api/v1/recommendation/build-knowledge-base
 * Fire-and-forget — call without awaiting for non-blocking UX.
 */
export async function buildKnowledgeBase(
  restaurantName: string,
  location: string,
  placeId?: string,
): Promise<void> {
  const body: Record<string, string> = { restaurant_name: restaurantName, location };
  if (placeId) body.place_id = placeId;

  await fetch(`${API_BASE}/api/v1/recommendation/build-knowledge-base`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * GET /api/v1/recommendation/dish/{dishName}
 */
export async function getDishContext(
  dishName: string,
  restaurantName: string,
  location: string,
): Promise<DishContextResponse> {
  const params = new URLSearchParams({ restaurant_name: restaurantName, location });
  const res = await fetch(
    `${API_BASE}/api/v1/recommendation/dish/${encodeURIComponent(dishName)}?${params}`,
  );
  return handleResponse<DishContextResponse>(res);
}

// ─── Dish Images ──────────────────────────────────────────────────────────────

/**
 * GET /api/v1/dish-image/
 * Returns a locally-cached image URL; fetches from DuckDuckGo on first call.
 */
export async function getDishImage(
  dishName: string,
  restaurantName?: string,
): Promise<DishImageResponse> {
  const params = new URLSearchParams({ dish_name: dishName });
  if (restaurantName) params.set('restaurant_name', restaurantName);

  try {
    const res = await fetch(`${API_BASE}/api/v1/dish-image/?${params}`);
    if (!res.ok) return { image_url: null, cached: false };
    return res.json() as Promise<DishImageResponse>;
  } catch {
    return { image_url: null, cached: false };
  }
}
