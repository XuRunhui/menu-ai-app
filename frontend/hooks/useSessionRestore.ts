'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { getMenu, getPlaceDetails } from '@/lib/api';
import { forgetMenu, forgetRestaurant, menuCopy } from '@/lib/localHistory';
import { useAppContext } from '@/context/AppContext';

export type RestoreStatus = 'ready' | 'restoring' | 'unavailable';

/**
 * Makes sure the results in memory are the ones the URL names, loading them if not.
 *
 * ?menu= is a parsed menu's id and ?place= a Google place id. Results for anything else are left
 * over from before, such as an uploaded menu still in memory when the assistant opens a restaurant,
 * and are replaced rather than shown under the new name. Menus come from this browser's copy
 * first, since the demo server forgets them whenever it restarts.
 */
export function useSessionRestore(): RestoreStatus {
  const searchParams = useSearchParams();
  const menuId = searchParams.get('menu');
  const placeId = searchParams.get('place');

  const { parsedMenu, placeDetails, openMenu, openPlace } = useAppContext();

  const showing = menuId
    ? parsedMenu?.menu_id === menuId
    : placeId
      ? !parsedMenu && placeDetails?.place?.place_id === placeId
      : Boolean(parsedMenu || placeDetails);
  const target = menuId ? `menu:${menuId}` : placeId ? `place:${placeId}` : null;
  const [failedFor, setFailedFor] = useState<string | null>(null);
  const failed = target !== null && failedFor === target;

  useEffect(() => {
    if (showing || !target || failed) return;
    let cancelled = false;

    (async () => {
      try {
        if (menuId) {
          const record = menuCopy(menuId) ?? (await getMenu(menuId));
          if (cancelled) return;
          openMenu(
            { ...record.parsed_menu, menu_id: record.menu_id },
            record.target_language || null,
            record.restaurant_name || null
          );
        } else if (placeId) {
          const details = await getPlaceDetails(placeId);
          if (cancelled) return;
          openPlace(details);
        }
      } catch {
        // No copy here and the server has restarted since: the saved link has outlived its menu.
        if (menuId) forgetMenu(menuId);
        else if (placeId) forgetRestaurant(placeId);
        if (!cancelled) setFailedFor(target);
      }
    })();

    return () => { cancelled = true; };
  }, [showing, target, failed, menuId, placeId, openMenu, openPlace]);

  if (showing) return 'ready';
  if (!target || failed) return 'unavailable';
  return 'restoring';
}
