/**
 * API client for the Menu AI backend.
 */

import type {
  ComboResponse,
  MenuRecord,
  MenuSourceKind,
  ParsedMenu,
  RestaurantHistoryItem,
  SavedMenuDetail,
  SavedMenuSummary,
} from './types';

// Empty by default: requests go to the same origin and Next.js rewrites proxy them to the
// backend (see next.config.ts). Set NEXT_PUBLIC_API_URL to call a backend directly instead.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

/**
 * Backend-built image URLs embed the host the backend saw (e.g. 127.0.0.1:8000 behind the
 * proxy), which the browser can't reach. Re-root /dish-images/ paths onto API_BASE_URL.
 */
export function resolveDishImageUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  const index = url.indexOf('/dish-images/');
  return index === -1 ? url : `${API_BASE_URL}${url.slice(index)}`;
}

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
  targetLanguage?: string | null,
  restaurantName?: string | null
): Promise<ParsedMenu> {
  const formData = new FormData();
  formData.append('image', imageFile);

  if (targetLanguage) {
    formData.append('target_language', targetLanguage);
  }
  if (restaurantName) {
    formData.append('restaurant_name', restaurantName);
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/menu/parse`, {
    method: 'POST',
    body: formData,
    // Sends the session cookie so signed-in users' menus are saved to their library.
    credentials: 'include',
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
 * @param label - Optional search text to show in the signed-in user's history
 * @returns Place details with reviews and popular dishes
 * @throws Error if the API request fails
 */
export async function getPlaceDetails(placeId: string, label?: string): Promise<PlaceDetailsResponse> {
  // label = the user's own search text; saved to their restaurant history when signed in.
  const params = label ? `?${new URLSearchParams({ label })}` : '';
  const response = await fetch(`${API_BASE_URL}/api/v1/places/${encodeURIComponent(placeId)}${params}`, {
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error ${response.status}`);
  }

  return response.json();
}

export interface TasteTextureRound {
  tastes: string[];
  textures: string[];
  flavor_profile: string;
  confidence: number;
}

export interface TasteTextureResponse {
  dish_name: string;
  /** From the menu's description alone. */
  round1: TasteTextureRound;
  /** Refined with what reviewers said, when any review mentions the dish. */
  round2: TasteTextureRound | null;
  improvement_score: number | null;
}

// One prediction per dish and description for the whole visit: the backend caches the model's
// answer, but every request still counts toward the visitor's hourly allowance.
const tasteTextures = new Map<string, Promise<TasteTextureResponse>>();

/**
 * How a dish tastes and feels, predicted by DeepSeek from the menu's description and refined with
 * review quotes that mention it. Works for uploaded menus and restaurants alike.
 */
export function predictTasteTexture(
  dishName: string,
  description: string,
  reviewExcerpts: string[] = []
): Promise<TasteTextureResponse> {
  const key = [dishName, description, ...reviewExcerpts].join('\n');
  const known = tasteTextures.get(key);
  if (known) return known;

  const request = fetch(`${API_BASE_URL}/api/v1/recommendation/taste-texture`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dish_name: dishName,
      description,
      include_reviews: reviewExcerpts.length > 0,
      review_excerpts: reviewExcerpts,
    }),
  }).then(async (response) => {
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    return (await response.json()) as TasteTextureResponse;
  });
  tasteTextures.set(key, request);
  request.catch(() => tasteTextures.delete(key)); // a refusal or an error can be tried again later
  return request;
}

export interface DishImageResponse {
  image_url: string | null;
  cached: boolean;
  /** Credit line required by the photo's license (e.g. Wikimedia Commons). */
  attribution?: string;
  source?: string;
}

type DishImageExtras = { translatedName?: string | null; description?: string | null };

interface DishImageEntry {
  promise: Promise<DishImageResponse>;
  /** Set once the answer is in, so a card that mounts again can show it without waiting. */
  answer?: DishImageResponse;
  /** When a failed request may be tried again; answers that came back never expire. */
  retryAfter?: number;
}

// One request per dish for the whole visit. Cards mount again on every category switch and every
// time the combined menu updates, and asking each time sent 200 requests for 41 dishes on one
// page. The key matches the server's cache: restaurant and dish name, nothing else.
const dishImages = new Map<string, DishImageEntry>();
const RETRY_FAILED_IMAGE_MS = 60_000;
const NO_IMAGE: DishImageResponse = { image_url: null, cached: false };

function dishImageKey(dishName: string, restaurantName?: string): string {
  return `${(restaurantName ?? '').trim().toLowerCase()}\n${dishName.trim().toLowerCase()}`;
}

/** The photo already found for this dish during this visit, if any. */
export function knownDishImage(dishName: string, restaurantName?: string): DishImageResponse | null {
  return dishImages.get(dishImageKey(dishName, restaurantName))?.answer ?? null;
}

/**
 * The dish's photo, found and judged by the backend on first request and cached there for everyone.
 * Asked at most once per visit; a refusal (the hourly search limit) or an error is retried after
 * a minute.
 *
 * @param dishName - Name of the dish
 * @param restaurantName - Restaurant name used to scope the image search
 * @returns Image URL pointing to the locally-cached file, or null if not found
 */
export function getDishImage(
  dishName: string,
  restaurantName?: string,
  // What the menu says about the dish. Only used on a cache miss, to search and judge better:
  // "Ba-corn" alone looks like a corn dog; "sweet corn, bacon, mozzarella" says corn cheese.
  extras: DishImageExtras = {}
): Promise<DishImageResponse> {
  const key = dishImageKey(dishName, restaurantName);
  const known = dishImages.get(key);
  if (known && (known.retryAfter === undefined || known.retryAfter > Date.now())) return known.promise;

  const entry: DishImageEntry = { promise: Promise.resolve(NO_IMAGE) };
  entry.promise = requestDishImage(dishName, restaurantName, extras).then(({ answer, final }) => {
    entry.answer = answer;
    if (!final) entry.retryAfter = Date.now() + RETRY_FAILED_IMAGE_MS;
    return answer;
  });
  dishImages.set(key, entry);
  return entry.promise;
}

/** One request to the backend. `final` is false when it's worth asking again later. */
async function requestDishImage(
  dishName: string,
  restaurantName: string | undefined,
  extras: DishImageExtras
): Promise<{ answer: DishImageResponse; final: boolean }> {
  const params = new URLSearchParams({ dish_name: dishName });
  if (restaurantName) params.set('restaurant_name', restaurantName);
  if (extras.translatedName && extras.translatedName !== dishName) {
    params.set('translated_name', extras.translatedName.slice(0, 300));
  }
  if (extras.description) params.set('description', extras.description.slice(0, 600));

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/dish-image?${params}`);
    if (!response.ok) return { answer: NO_IMAGE, final: false };
    const data: DishImageResponse = await response.json();
    return { answer: { ...data, image_url: resolveDishImageUrl(data.image_url) }, final: true };
  } catch {
    return { answer: NO_IMAGE, final: false };
  }
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: number;
  username: string;
  email?: string | null;
  created_at: string;
}

async function authRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth${path}`, {
    ...init,
    // Session lives in an httpOnly cookie; include it even if the API is on another origin.
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    // FastAPI validation errors (422) return a list of issues rather than a string.
    const detail = Array.isArray(error.detail)
      ? 'Please check your username and password format.'
      : error.detail;
    throw new Error(detail || `HTTP error ${response.status}`);
  }

  return response.status === 204 ? (undefined as T) : response.json();
}

export function registerUser(username: string, password: string): Promise<AuthUser> {
  return authRequest('/register', { method: 'POST', body: JSON.stringify({ username, password }) });
}

export function loginUser(username: string, password: string): Promise<AuthUser> {
  return authRequest('/login', { method: 'POST', body: JSON.stringify({ username, password }) });
}

export function logoutUser(): Promise<void> {
  return authRequest('/logout', { method: 'POST' });
}

export function loginWithGoogleCredential(credential: string): Promise<AuthUser> {
  return authRequest('/google', { method: 'POST', body: JSON.stringify({ credential }) });
}

export interface AuthConfig {
  auth_enabled: boolean;
  google_client_id: string | null;
}

export async function getAuthConfig(): Promise<AuthConfig> {
  try {
    return await authRequest('/config');
  } catch {
    return { auth_enabled: false, google_client_id: null };
  }
}

/** Returns the signed-in user, or null when there is no valid session. */
export async function getCurrentUser(): Promise<AuthUser | null> {
  try {
    return await authRequest<AuthUser>('/me');
  } catch {
    return null;
  }
}

// ─── Menus (shared cache) and library (accounts mode) ─────────────────────────

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
    headers: init?.body ? { 'Content-Type': 'application/json', ...init?.headers } : init?.headers,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(typeof error.detail === 'string' ? error.detail : `HTTP error ${response.status}`);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

/** A parsed menu by its shared id, used to restore /results?menu=<id> after a refresh. */
export function getMenu(menuId: string): Promise<MenuRecord> {
  return jsonRequest(`/api/v1/menus/${encodeURIComponent(menuId)}`);
}

export function listSavedMenus(): Promise<SavedMenuSummary[]> {
  return jsonRequest('/api/v1/me/menus');
}

export function getSavedMenu(id: number): Promise<SavedMenuDetail> {
  return jsonRequest(`/api/v1/me/menus/${id}`);
}

export function deleteSavedMenu(id: number): Promise<void> {
  return jsonRequest(`/api/v1/me/menus/${id}`, { method: 'DELETE' });
}

export function listRestaurantHistory(): Promise<RestaurantHistoryItem[]> {
  return jsonRequest('/api/v1/me/restaurants');
}

export function deleteRestaurantHistory(placeId: string): Promise<void> {
  return jsonRequest(`/api/v1/me/restaurants/${encodeURIComponent(placeId)}`, { method: 'DELETE' });
}

// ─── Knowledge ────────────────────────────────────────────────────────────────

export interface ComboDishInput {
  name: string;
  description?: string | null;
  category?: string | null;
}

export function getCombos(dishes: ComboDishInput[], maxCombos = 3, restaurantName?: string | null): Promise<ComboResponse> {
  return jsonRequest('/api/v1/knowledge/combos', {
    method: 'POST',
    body: JSON.stringify({ dishes, max_combos: maxCombos, restaurant_name: restaurantName || null }),
  });
}

// ─── AI dining assistant ──────────────────────────────────────────────────────

/**
 * One entry in the conversation, in the shape the model expects.
 *
 * `tool_calls` / `tool_call_id` are opaque here: the browser stores them and hands them straight
 * back so a later turn still knows what an earlier search returned. Nothing is kept server-side,
 * so refreshing the page starts a new conversation.
 */
export interface AssistantMessage {
  role: 'user' | 'assistant' | 'tool';
  content: string;
  tool_calls?: unknown[];
  tool_call_id?: string;
  name?: string;
}

/** What the browser knows about where the diner is. All of it optional. */
export interface DinerContext {
  latitude?: number;
  longitude?: number;
  location_text?: string;
  radius_km?: number;
}

export interface AssistantRestaurant {
  place_id: string;
  name: string;
  address?: string;
  rating?: number;
  user_ratings_total?: number;
  price_level?: number;
  open_now?: boolean;
  distance_km?: number;
}

/**
 * Offer to read a menu photo, set when the assistant has no menu for a place.
 *
 * Menuist reads menus from photographs and has no way to fetch one from the web, so
 * "what's on the menu?" can only be answered from review chatter. `reason` says which:
 * `reviews_only` means dishes reviewers named, `no_menu_online` means nothing was found at all.
 */
export interface MenuUploadOffer {
  restaurant_name: string;
  place_id: string;
  reason: 'no_menu_online' | 'reviews_only';
}

/**
 * A restaurant's menu as the assistant read it from its website.
 * `results` carries each source's own menu and report, so the results page can label dishes by
 * source and merge in a photo the diner adds later.
 */
export interface FoundMenu {
  restaurant_name: string;
  place_id: string;
  combined: CombinedMenu;
  results: SourceResult[];
}

export interface AssistantResponse {
  reply: string;
  messages: AssistantMessage[];
  restaurants: AssistantRestaurant[];
  quick_replies: string[];
  tools_used: string[];
  /** False when the deployment has no DeepSeek key and the scripted flow answered instead. */
  llm_available: boolean;
  /** True when asking for browser location permission would help. */
  needs_location: boolean;
  /** Present when the UI should offer to parse a photo of the restaurant's menu. */
  menu_upload?: MenuUploadOffer | null;
  /** Present when read_menu found dishes in at least one source. */
  found_menu?: FoundMenu | null;
}

export function sendAssistantMessage(
  messages: AssistantMessage[],
  context: DinerContext = {}
): Promise<AssistantResponse> {
  return jsonRequest('/api/v1/assistant/chat', {
    method: 'POST',
    body: JSON.stringify({ messages, context }),
  });
}

// ─── Menus from several sources ───────────────────────────────────────────────

export type SourceStatus = 'found' | 'none' | 'unavailable' | 'error';

/** What happened when one source was checked, written for the diner. */
export interface SourceReport {
  kind: MenuSourceKind;
  status: SourceStatus;
  item_count: number;
  detail: string;
  url?: string | null;
}

export interface SourceResult {
  report: SourceReport;
  menu?: ParsedMenu | null;
  /** Website only: false when the listed site no longer belongs to the restaurant. */
  website_trusted?: boolean | null;
}

export interface SourcedMenu {
  kind: MenuSourceKind;
  menu: ParsedMenu;
}

export interface ReviewDishInput {
  name: string;
  mention_count?: number;
}

export interface SourceCount {
  kind: MenuSourceKind;
  items: number;
  only_here: number;
}

export interface CombinedMenu {
  menu: ParsedMenu;
  total_items: number;
  by_source: SourceCount[];
  /** A nudge, never a decision: whether a photo of the real menu would likely help. */
  suggest_upload: boolean;
  suggestion: string;
}

/** Look for the place's menu in one source (today, only its own website). */
export function readMenuSource(
  kind: 'website',
  placeId: string,
  targetLanguage: string | null = 'English'
): Promise<SourceResult> {
  return jsonRequest(`/api/v1/menus/sources/${kind}`, {
    method: 'POST',
    body: JSON.stringify({ place_id: placeId, target_language: targetLanguage }),
  });
}

/** Merge per-source menus and review dishes into one labelled menu. Free: no model calls. */
export function combineMenus(sources: SourcedMenu[], reviewDishes: ReviewDishInput[]): Promise<CombinedMenu> {
  return jsonRequest('/api/v1/menus/combine', {
    method: 'POST',
    body: JSON.stringify({ sources, review_dishes: reviewDishes }),
  });
}
