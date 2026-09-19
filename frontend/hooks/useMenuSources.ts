'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAppContext, type MenuSourcesState } from '@/context/AppContext';
import {
  combineMenus,
  getMenu,
  parseMenu,
  readMenuSource,
  type SourcedMenu,
  type SourceResult,
} from '@/lib/api';
import type { ParsedMenu } from '@/lib/types';
import {
  forgetRestaurantPhotos,
  keepMenuCopy,
  menuCopy,
  menuRecord,
  rememberRestaurantPhoto,
  restaurantPhotoIds,
} from '@/lib/localHistory';

const READABLE = ['website'] as const;
type ReadableKind = (typeof READABLE)[number];

/** Every source that produced a menu, plus the diner's photos, ready to be combined. */
function sourcedMenus(state: MenuSourcesState): SourcedMenu[] {
  const found: SourcedMenu[] = [];
  for (const kind of READABLE) {
    const menu = state[kind]?.menu;
    if (menu?.menu?.length) found.push({ kind, menu });
  }
  return [...found, ...state.uploads];
}

/** Adds a photo's menu, unless the same photo (same parsed-menu id) is already in. */
function withUpload(state: MenuSourcesState, menu: ParsedMenu): MenuSourcesState {
  if (menu.menu_id && state.uploads.some((upload) => upload.menu.menu_id === menu.menu_id)) return state;
  return { ...state, uploads: [...state.uploads, { kind: 'upload', menu }] };
}

function failed(kind: ReadableKind): SourceResult {
  return { report: { kind, status: 'error', item_count: 0, detail: "Couldn't check this source right now." } };
}

/**
 * Builds the place's menu from every source, and keeps it combined as sources arrive.
 *
 * Mount this once per results page (MenuSourcesPanel does): it starts the lookups, and its effect
 * re-combines whenever a source or a photo arrives. Everything else reads `menuSources` from
 * context. None of the sources stops the others: each usually has only part of the menu.
 */
export function useMenuSources() {
  const { placeDetails, popularDishes, restaurant, targetLanguage, menuSources, updateMenuSources } =
    useAppContext();
  const placeId = placeDetails?.place?.place_id ?? null;
  // Every source is read into one language, so the same dish can be recognised across them.
  const language = targetLanguage ?? 'English';

  const [uploading, setUploading] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const startedFor = useRef<string | null>(null);
  const photosFor = useRef<string | null>(null);
  const combineRun = useRef(0);

  const reviewDishes = useMemo(
    () => popularDishes.map((dish) => ({ name: dish.name, mention_count: dish.mention_count || 1 })),
    [popularDishes]
  );

  // Start the lookups once per place. The ref stops React's development double-run from paying
  // for a second website read; the context check skips places already done, including ones the
  // assistant looked up before handing over.
  useEffect(() => {
    if (!placeId || startedFor.current === placeId || menuSources?.placeId === placeId) return;
    startedFor.current = placeId;
    updateMenuSources(() => ({ placeId, uploads: [], combined: null }));

    for (const kind of READABLE) {
      readMenuSource(kind, placeId, language)
        .catch(() => failed(kind))
        .then((result) =>
          updateMenuSources((current) =>
            current?.placeId === placeId ? { ...current, [kind]: result } : current
          )
        );
    }
  }, [placeId, language, menuSources?.placeId, updateMenuSources]);

  // Photos the diner added on an earlier visit come back with the restaurant, from this browser's
  // copy when there is one: the demo server forgets parsed menus whenever it restarts.
  useEffect(() => {
    if (!placeId || menuSources?.placeId !== placeId || photosFor.current === placeId) return;
    photosFor.current = placeId;
    for (const id of restaurantPhotoIds(placeId)) {
      const copy = menuCopy(id);
      (copy ? Promise.resolve(copy) : getMenu(id))
        .then((record) =>
          updateMenuSources((current) =>
            current?.placeId === placeId
              ? withUpload(current, { ...record.parsed_menu, menu_id: record.menu_id })
              : current
          )
        )
        .catch(() => forgetRestaurantPhotos(placeId, id));
    }
  }, [placeId, menuSources?.placeId, updateMenuSources]);

  // Re-combine whenever the inputs change. Combining is free (no model calls), and the run
  // counter makes sure a slow, older response never overwrites a newer one.
  const website = menuSources?.website;
  const uploads = menuSources?.uploads;
  useEffect(() => {
    if (!menuSources || menuSources.placeId !== placeId) return;
    const run = ++combineRun.current;
    const forPlace = menuSources.placeId;
    combineMenus(sourcedMenus(menuSources), reviewDishes)
      .then((combined) => {
        if (run !== combineRun.current) return;
        updateMenuSources((current) => (current?.placeId === forPlace ? { ...current, combined } : current));
      })
      .catch(() => {}); // keep the last combined menu
    // Only the source inputs matter here; `combined` changing must not trigger another run.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [website, uploads, reviewDishes, placeId]);

  /** Read the diner's menu photos (several pages at once) and merge them in as they finish. */
  const addPhotos = useCallback(
    async (files: File[]) => {
      if (!placeId || files.length === 0) return;
      setUploadError(null);
      setUploading((count) => count + files.length);
      await Promise.all(
        files.map(async (file) => {
          try {
            const menu = await parseMenu(file, language, restaurant?.name ?? null);
            updateMenuSources((current) => (current?.placeId === placeId ? withUpload(current, menu) : current));
            if (menu.menu_id) {
              // Saved with the restaurant, so reopening it from History brings this photo back.
              keepMenuCopy(menuRecord({ ...menu, menu_id: menu.menu_id }, restaurant?.name ?? null, language));
              rememberRestaurantPhoto(placeId, restaurant?.name ?? 'Restaurant', menu.menu_id);
            }
          } catch (error) {
            setUploadError(
              error instanceof Error ? error.message : "Couldn't read that photo. Try a sharper one."
            );
          } finally {
            setUploading((count) => count - 1);
          }
        })
      );
    },
    [placeId, language, restaurant?.name, updateMenuSources]
  );

  /** Takes the diner's photos out of this restaurant's menu, now and the next time it's opened. */
  const removePhotos = useCallback(() => {
    if (!placeId) return;
    forgetRestaurantPhotos(placeId);
    updateMenuSources((current) => (current?.placeId === placeId ? { ...current, uploads: [] } : current));
  }, [placeId, updateMenuSources]);

  const checking = READABLE.filter((kind) => menuSources?.placeId === placeId && !menuSources?.[kind]);

  return {
    menuSources,
    checking,
    addPhotos,
    removePhotos,
    uploading,
    uploadError,
    reviewCount: reviewDishes.length,
  };
}
