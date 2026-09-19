'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FileText, Loader2, MapPin, Trash2 } from 'lucide-react';
import AppHeader from '@/components/layout/AppHeader';
import { useAppContext } from '@/context/AppContext';
import { useAuth } from '@/context/AuthContext';
import {
  deleteRestaurantHistory,
  deleteSavedMenu,
  listRestaurantHistory,
  listSavedMenus,
} from '@/lib/api';
import {
  forgetMenu,
  forgetRestaurant,
  listLocalMenus,
  listLocalRestaurants,
  restaurantPhotoIds,
} from '@/lib/localHistory';

interface MenuRow {
  key: string;
  menuId: string | null;
  title: string;
  meta: string;
  remove: () => Promise<void> | void;
}

interface RestaurantRow {
  placeId: string;
  title: string;
  meta: string;
  remove: () => Promise<void> | void;
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

/** "Viewed Sep 18 · 2 menu photos added": those photos come back when the place is reopened. */
function restaurantMeta(placeId: string, viewedAt: string) {
  const photos = restaurantPhotoIds(placeId).length;
  return [`Viewed ${formatDate(viewedAt)}`, photos && `${photos} menu photo${photos === 1 ? '' : 's'} added`]
    .filter(Boolean)
    .join(' · ');
}

function Row({ icon: Icon, title, meta, onOpen, onDelete }: {
  icon: typeof FileText;
  title: string;
  meta: string;
  onOpen?: () => void;
  onDelete: () => void;
}) {
  return (
    <li className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
      <Icon className="w-4 h-4 text-muted-foreground shrink-0" />
      <button onClick={onOpen} disabled={!onOpen} className="flex-1 min-w-0 text-left group disabled:cursor-default">
        <p className="text-sm font-medium text-foreground truncate group-enabled:group-hover:text-primary transition-colors">{title}</p>
        <p className="text-xs text-muted-foreground">{meta}</p>
      </button>
      <button onClick={onDelete} aria-label={`Remove ${title}`} className="text-muted-foreground hover:text-red-600 transition-colors">
        <Trash2 className="w-4 h-4" />
      </button>
    </li>
  );
}

export default function HistoryPage() {
  const router = useRouter();
  const { authEnabled, user, loading: authLoading } = useAuth();
  const { resetSession } = useAppContext();
  const [menus, setMenus] = useState<MenuRow[]>([]);
  const [restaurants, setRestaurants] = useState<RestaurantRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const useServerLibrary = authEnabled && Boolean(user);

  const load = useCallback(async () => {
    try {
      if (useServerLibrary) {
        const [savedMenus, history] = await Promise.all([listSavedMenus(), listRestaurantHistory()]);
        setMenus(savedMenus.map((menu) => ({
          key: `server-${menu.id}`,
          menuId: menu.menu_id,
          title: menu.restaurant_name || `${menu.detected_language ?? 'Parsed'} menu`,
          meta: [`${menu.item_count} dishes`, menu.target_language && `translated to ${menu.target_language}`,
            formatDate(menu.updated_at)].filter(Boolean).join(' · '),
          remove: () => deleteSavedMenu(menu.id),
        })));
        setRestaurants(history.map((item) => ({
          placeId: item.place_id,
          title: item.label || 'Restaurant',
          meta: restaurantMeta(item.place_id, item.viewed_at),
          remove: () => deleteRestaurantHistory(item.place_id),
        })));
      } else {
        setMenus(listLocalMenus().map((menu) => ({
          key: `local-${menu.menuId}`,
          menuId: menu.menuId,
          title: menu.label,
          meta: [`${menu.itemCount} dishes`, menu.targetLanguage && `translated to ${menu.targetLanguage}`,
            formatDate(menu.savedAt)].filter(Boolean).join(' · '),
          remove: () => forgetMenu(menu.menuId),
        })));
        setRestaurants(listLocalRestaurants().map((item) => ({
          placeId: item.placeId,
          title: item.label,
          meta: restaurantMeta(item.placeId, item.viewedAt),
          remove: () => forgetRestaurant(item.placeId),
        })));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load your history.');
    } finally {
      setLoading(false);
    }
  }, [useServerLibrary]);

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  // Opening an item clears the current session; the results page restores it from the URL.
  const open = (query: string) => {
    resetSession();
    router.push(`/results${query}`);
  };

  const showSignInPrompt = authEnabled && !authLoading && !user;

  return (
    <main className="min-h-screen bg-background flex flex-col">
      <AppHeader showBack backHref="/" />

      <div className="flex-1 max-w-2xl mx-auto w-full px-6 py-12 space-y-10">
        <div className="opacity-0 animate-fade-slide-up stagger-1">
          <p className="text-xs font-medium tracking-widest uppercase text-primary/70 mb-3">
            {useServerLibrary ? 'Your library' : 'On this device'}
          </p>
          <h1 className="font-display text-4xl font-light text-foreground">History</h1>
        </div>

        {showSignInPrompt && (
          <p className="text-sm text-muted-foreground">
            Showing history from this browser. <Link href="/login?next=/history" className="text-primary hover:underline">Sign in</Link>{' '}
            to keep it across devices.
          </p>
        )}

        {(authLoading || loading) && <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />}
        {error && <p className="text-sm text-red-700">{error}</p>}

        {!authLoading && !loading && (
          <>
            <section className="space-y-3">
              <h2 className="text-sm font-medium text-foreground">Menus</h2>
              {menus.length === 0 ? (
                <p className="text-sm text-muted-foreground">Menus you upload appear here.</p>
              ) : (
                <ul className="space-y-2">
                  {menus.map((menu) => (
                    <Row
                      key={menu.key}
                      icon={FileText}
                      title={menu.title}
                      meta={menu.meta}
                      onOpen={menu.menuId ? () => open(`?menu=${menu.menuId}`) : undefined}
                      onDelete={async () => {
                        await menu.remove();
                        setMenus((items) => items.filter((m) => m.key !== menu.key));
                      }}
                    />
                  ))}
                </ul>
              )}
            </section>

            <section className="space-y-3">
              <h2 className="text-sm font-medium text-foreground">Restaurants</h2>
              {restaurants.length === 0 ? (
                <p className="text-sm text-muted-foreground">Restaurants you open appear here.</p>
              ) : (
                <ul className="space-y-2">
                  {restaurants.map((item) => (
                    <Row
                      key={item.placeId}
                      icon={MapPin}
                      title={item.title}
                      meta={item.meta}
                      onOpen={() => open(`?place=${encodeURIComponent(item.placeId)}`)}
                      onDelete={async () => {
                        await item.remove();
                        setRestaurants((items) => items.filter((r) => r.placeId !== item.placeId));
                      }}
                    />
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  );
}
