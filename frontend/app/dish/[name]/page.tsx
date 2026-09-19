'use client';

import { Suspense, use, useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Separator } from '@/components/ui/separator';
import AppHeader from '@/components/layout/AppHeader';
import DishHero from '@/components/dish/DishHero';
import DishLLMSummary from '@/components/dish/DishLLMSummary';
import DishReviewInsight from '@/components/dish/DishReviewInsight';
import { useAppContext } from '@/context/AppContext';
import { useSessionRestore } from '@/hooks/useSessionRestore';
import { getDishImage, knownDishImage, predictTasteTexture, type TasteTextureResponse } from '@/lib/api';
import { findPopularDish } from '@/lib/utils/dishMatcher';
import type { DishContextResponse } from '@/lib/types';

interface DishPageProps {
  params: Promise<{ name: string }>;
}

export default function DishPage({ params }: DishPageProps) {
  const { name: encodedName } = use(params);
  // useSearchParams (in useSessionRestore) needs a Suspense boundary.
  return (
    <Suspense>
      <DishContent dishName={decodeURIComponent(encodedName)} />
    </Suspense>
  );
}

function DishContent({ dishName }: { dishName: string }) {
  const router = useRouter();
  const restore = useSessionRestore();

  const { restaurant, parsedMenu, placeDetails, menuSources, popularDishes, resultsQuery, targetLanguage } =
    useAppContext();
  // Usually the card on the results page has already found the photo.
  const [dishImageUrl, setDishImageUrl] = useState<string | null>(
    () => knownDishImage(dishName, restaurant?.name)?.image_url ?? null
  );
  const [dishImageCredit, setDishImageCredit] = useState(
    () => knownDishImage(dishName, restaurant?.name)?.attribution ?? ''
  );

  // The dish as the menu lists it: an uploaded menu, or the menu combined from a restaurant's sources.
  const combined =
    menuSources && menuSources.placeId === placeDetails?.place?.place_id ? menuSources.combined : null;
  const menuItem = useMemo(() => {
    const categories = parsedMenu?.menu ?? combined?.menu.menu ?? [];
    for (const cat of categories) {
      const item = cat.items.find((i) => i.name.toLowerCase() === dishName.toLowerCase());
      if (item) return item;
    }
    return null;
  }, [parsedMenu, combined, dishName]);

  // What reviewers said about it: the restaurant's Google reviews, fetched with the restaurant.
  const reviewed = useMemo(() => findPopularDish(dishName, popularDishes), [dishName, popularDishes]);
  const quotes = useMemo(() => reviewed?.sample_reviews ?? [], [reviewed]);

  // How it tastes and feels, from the menu's description and those quotes: one cached DeepSeek call.
  // Without a description there is nothing to go on, and the page shows what the menu says.
  const description = menuItem?.description_translated || menuItem?.description || '';
  const insightKey = description ? `${dishName}\n${description}` : null;
  const [insight, setInsight] = useState<{ key: string; result: TasteTextureResponse | null } | null>(null);
  const current = insight && insight.key === insightKey ? insight : null;
  const thinking = Boolean(insightKey) && !current;
  useEffect(() => {
    if (!insightKey) return;
    let cancelled = false;
    predictTasteTexture(dishName, description, quotes)
      .then((result) => { if (!cancelled) setInsight({ key: insightKey, result }); })
      // No insight is fine: the description and the quotes still show.
      .catch(() => { if (!cancelled) setInsight({ key: insightKey, result: null }); });
    return () => { cancelled = true; };
  }, [insightKey, dishName, description, quotes]);

  const context: DishContextResponse | null =
    current?.result || quotes.length > 0
      ? {
          dish_name: dishName,
          menu_description: null,
          review_count: reviewed?.mention_count ?? quotes.length,
          review_excerpts: quotes,
          metadata: {},
          is_popular: Boolean(reviewed),
          popularity_score: 0,
          taste_texture: current?.result
            ? { round1: current.result.round1, round2: current.result.round2 ?? undefined }
            : undefined,
        }
      : null;

  // Redirect home when there is nothing to show (guests lose results on refresh by design)
  useEffect(() => {
    if (restore === 'unavailable') {
      router.replace('/');
    }
  }, [restore, router]);

  // The dish's photo, if the results page hasn't found it already.
  // restaurantName is optional — backend searches by dish name alone when absent.
  useEffect(() => {
    if (dishImageUrl) return;
    let cancelled = false;
    getDishImage(dishName, restaurant?.name, {
      translatedName: menuItem?.name_translated,
      description: menuItem?.description_translated || menuItem?.description,
    }).then((data) => {
      if (!cancelled && data.image_url) {
        setDishImageUrl(data.image_url);
        setDishImageCredit(data.attribution ?? '');
      }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [dishName, restaurant, dishImageUrl]);

  if (restore !== 'ready' || (!parsedMenu && !placeDetails)) {
    return (
      <main className="min-h-screen bg-background flex flex-col">
        <AppHeader showBack backHref={`/results${resultsQuery}`} />
        <p className="text-center text-sm text-muted-foreground py-24">Loading your saved results…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background flex flex-col">
      <AppHeader showBack backHref={`/results${resultsQuery}`} />

      {/* Hero — the dish's own photo, or the placeholder. Never a restaurant photo standing in for it. */}
      <DishHero
        name={dishName}
        photoUrl={dishImageUrl}
        credit={dishImageUrl ? dishImageCredit : ''}
        subtitle={targetLanguage ? menuItem?.name_translated : null}
      />

      {/* Content */}
      <div className="flex-1 max-w-2xl mx-auto w-full px-6 py-8 space-y-8">

        {/* Description / LLM Summary */}
        <section className="opacity-0 animate-fade-slide-up stagger-1">
          <DishLLMSummary
            loading={false}
            tagsLoading={thinking}
            context={context}
            fallbackDescription={menuItem?.description ?? null}
            translatedDescription={targetLanguage ? menuItem?.description_translated ?? null : null}
          />
        </section>

        {/* Review Insights */}
        {quotes.length > 0 && (
          <>
            <Separator />
            <section className="opacity-0 animate-fade-slide-up stagger-2">
              <DishReviewInsight loading={false} excerpts={quotes} reviewCount={reviewed?.mention_count} />
            </section>
          </>
        )}

        {/* Nothing to say beyond the name and photo */}
        {!description && quotes.length === 0 && (
          <div className="rounded-xl border border-border bg-muted/30 px-6 py-8 text-center">
            <p className="text-muted-foreground text-sm">
              The menu doesn&apos;t describe this dish, and no review mentions it.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
