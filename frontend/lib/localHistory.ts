/**
 * Per-browser history for guest mode: menus and restaurants opened on this device.
 * Stored in localStorage; every access is guarded because storage can be unavailable.
 *
 * Parsed menus are also copied here, not just their ids. The demo server keeps menus only until it
 * restarts (it scales to zero when idle), and a history entry that can only be reopened from the
 * server stops working the next morning.
 */

import type { MenuRecord, ParsedMenu } from '@/lib/types';

export interface LocalMenuEntry {
  menuId: string;
  label: string;
  itemCount: number;
  targetLanguage: string | null;
  savedAt: string;
}

export interface LocalRestaurantEntry {
  placeId: string;
  label: string;
  viewedAt: string;
  /** Menu photos the diner added for this restaurant, by parsed-menu id, oldest first. */
  photoMenuIds?: string[];
}

const MENUS_KEY = 'menuist.history.menus';
const RESTAURANTS_KEY = 'menuist.history.restaurants';
const COPIES_KEY = 'menuist.history.menuCopies';
const COPY_PREFIX = 'menuist.menu.';
const MAX_ENTRIES = 50;
const MAX_COPIES = 30;
const MAX_PHOTOS_PER_RESTAURANT = 12;

function read<T>(key: string): T[] {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T[]) : [];
  } catch {
    return [];
  }
}

function write<T>(key: string, entries: T[]): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
  } catch {
    // Storage full or blocked: history is a convenience, so ignore.
  }
}

function remove(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore
  }
}

export function listLocalMenus(): LocalMenuEntry[] {
  return read<LocalMenuEntry>(MENUS_KEY);
}

export function listLocalRestaurants(): LocalRestaurantEntry[] {
  return read<LocalRestaurantEntry>(RESTAURANTS_KEY);
}

export function rememberMenu(entry: Omit<LocalMenuEntry, 'savedAt'>): void {
  const others = listLocalMenus().filter((m) => m.menuId !== entry.menuId);
  write(MENUS_KEY, [{ ...entry, savedAt: new Date().toISOString() }, ...others]);
}

/** Moves the restaurant to the top of the history, keeping the photos added for it. */
export function rememberRestaurant(entry: { placeId: string; label: string }): void {
  const restaurants = listLocalRestaurants();
  const existing = restaurants.find((r) => r.placeId === entry.placeId);
  const others = restaurants.filter((r) => r.placeId !== entry.placeId);
  write(RESTAURANTS_KEY, [{ ...existing, ...entry, viewedAt: new Date().toISOString() }, ...others]);
}

export function forgetMenu(menuId: string): void {
  write(MENUS_KEY, listLocalMenus().filter((m) => m.menuId !== menuId));
}

export function forgetRestaurant(placeId: string): void {
  write(RESTAURANTS_KEY, listLocalRestaurants().filter((r) => r.placeId !== placeId));
}

// ─── Menu photos added to a restaurant ─────────────────────────────────────────

/** Records a menu photo added on a restaurant's page, so reopening the restaurant brings it back. */
export function rememberRestaurantPhoto(placeId: string, label: string, menuId: string): void {
  const restaurants = listLocalRestaurants();
  const existing = restaurants.find((r) => r.placeId === placeId);
  const photoMenuIds = [...(existing?.photoMenuIds ?? []).filter((id) => id !== menuId), menuId].slice(
    -MAX_PHOTOS_PER_RESTAURANT
  );
  write(RESTAURANTS_KEY, [
    { placeId, label: existing?.label ?? label, viewedAt: new Date().toISOString(), photoMenuIds },
    ...restaurants.filter((r) => r.placeId !== placeId),
  ]);
}

export function restaurantPhotoIds(placeId: string): string[] {
  return listLocalRestaurants().find((r) => r.placeId === placeId)?.photoMenuIds ?? [];
}

/** Forgets one photo (it could no longer be read back), or all of a restaurant's photos. */
export function forgetRestaurantPhotos(placeId: string, menuId?: string): void {
  write(
    RESTAURANTS_KEY,
    listLocalRestaurants().map((r) =>
      r.placeId !== placeId
        ? r
        : { ...r, photoMenuIds: menuId ? (r.photoMenuIds ?? []).filter((id) => id !== menuId) : [] }
    )
  );
}

// ─── Copies of parsed menus ────────────────────────────────────────────────────

/** The record the server would return for a menu just parsed, for keeping a copy of it. */
export function menuRecord(
  menu: ParsedMenu & { menu_id: string },
  restaurantName: string | null,
  targetLanguage: string | null
): MenuRecord {
  const { menu_id, ...parsed } = menu;
  return {
    menu_id,
    restaurant_name: restaurantName?.trim() ?? '',
    target_language: targetLanguage ?? '',
    detected_language: menu.detected_language ?? null,
    item_count: menu.menu.reduce((sum, category) => sum + category.items.length, 0),
    parsed_menu: parsed,
  };
}

/** Keeps a copy of a parsed menu in this browser, dropping the oldest copies to make room. */
export function keepMenuCopy(record: MenuRecord): void {
  const ids = [record.menu_id, ...read<string>(COPIES_KEY).filter((id) => id !== record.menu_id)];
  ids.slice(MAX_COPIES).forEach((id) => remove(COPY_PREFIX + id));
  const kept = ids.slice(0, MAX_COPIES);

  const store = () => window.localStorage.setItem(COPY_PREFIX + record.menu_id, JSON.stringify(record));
  try {
    store();
  } catch {
    // Storage full: free the older half of the copies and try once more.
    kept.splice(Math.max(1, Math.ceil(kept.length / 2))).forEach((id) => remove(COPY_PREFIX + id));
    try {
      store();
    } catch {
      return;
    }
  }
  write(COPIES_KEY, kept);
}

export function menuCopy(menuId: string): MenuRecord | null {
  try {
    const raw = window.localStorage.getItem(COPY_PREFIX + menuId);
    return raw ? (JSON.parse(raw) as MenuRecord) : null;
  } catch {
    return null;
  }
}
