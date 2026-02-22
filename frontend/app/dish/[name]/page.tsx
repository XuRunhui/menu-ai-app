'use client';

import { use, useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Separator } from '@/components/ui/separator';
import AppHeader from '@/components/layout/AppHeader';
import DishHero from '@/components/dish/DishHero';
import DishLLMSummary from '@/components/dish/DishLLMSummary';
import DishReviewInsight from '@/components/dish/DishReviewInsight';
import { useAppContext } from '@/context/AppContext';
import { getDishContext, getDishImage } from '@/lib/api';
import type { DishContextResponse } from '@/lib/types';

interface DishPageProps {
  params: Promise<{ name: string }>;
}

export default function DishPage({ params }: DishPageProps) {
  const router = useRouter();
  const { name: encodedName } = use(params);
  const dishName = decodeURIComponent(encodedName);

  const { restaurant, parsedMenu, knowledgeBaseStatus, placeDetails } = useAppContext();

  const [context, setContext] = useState<DishContextResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dishImageUrl, setDishImageUrl] = useState<string | null>(null);

  // Find the dish in parsedMenu for fallback description
  const menuItem = useMemo(() => {
    if (!parsedMenu) return null;
    for (const cat of parsedMenu.menu) {
      const item = cat.items.find(
        (i) => i.name.toLowerCase() === dishName.toLowerCase()
      );
      if (item) return item;
    }
    return null;
  }, [parsedMenu, dishName]);

  // Redirect home if no data at all
  useEffect(() => {
    if (!parsedMenu && !placeDetails) {
      router.replace('/');
    }
  }, [parsedMenu, placeDetails, router]);

  // Fetch dish context when we have restaurant info and KB is not idle
  useEffect(() => {
    if (!restaurant?.name || knowledgeBaseStatus === 'idle') return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    getDishContext(dishName, restaurant.name, restaurant.location)
      .then((data) => {
        if (!cancelled) {
          setContext(data);
          // Use dish_image_url from context if the backend already cached it
          if (data.dish_image_url) setDishImageUrl(data.dish_image_url);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [dishName, restaurant, knowledgeBaseStatus]);

  // Fallback: if context didn't supply a dish image (not yet cached), fetch it.
  // restaurantName is optional — backend searches by dish name alone when absent.
  useEffect(() => {
    if (dishImageUrl) return;
    let cancelled = false;
    getDishImage(dishName, restaurant?.name).then((data) => {
      if (!cancelled && data.image_url) setDishImageUrl(data.image_url);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [dishName, restaurant, dishImageUrl]);

  // Restaurant photo as second-tier fallback for the hero
  const restaurantPhoto = placeDetails?.place?.photo_urls?.[0] ?? null;

  const hasContextData = Boolean(restaurant?.name) && knowledgeBaseStatus !== 'idle';
  const showLoading = loading || knowledgeBaseStatus === 'building';

  return (
    <main className="min-h-screen bg-background flex flex-col">
      <AppHeader showBack backHref="/results" />

      {/* Hero — prefer dish-specific image, fall back to restaurant photo */}
      <DishHero name={dishName} photoUrl={dishImageUrl ?? restaurantPhoto} />

      {/* Content */}
      <div className="flex-1 max-w-2xl mx-auto w-full px-6 py-8 space-y-8">

        {/* Description / LLM Summary */}
        <section className="opacity-0 animate-fade-slide-up stagger-1">
          <DishLLMSummary
            loading={showLoading && hasContextData}
            context={context}
            fallbackDescription={menuItem?.description ?? null}
          />
        </section>

        {/* Review Insights */}
        {(context?.review_excerpts?.length || showLoading) && (
          <>
            <Separator />
            <section className="opacity-0 animate-fade-slide-up stagger-2">
              <DishReviewInsight
                loading={showLoading && hasContextData}
                excerpts={context?.review_excerpts ?? []}
                reviewCount={context?.review_count}
              />
            </section>
          </>
        )}

        {/* Error state */}
        {error && !loading && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* No context available (upload-only path) */}
        {!hasContextData && !loading && !menuItem?.description && (
          <div className="rounded-xl border border-border bg-muted/30 px-6 py-8 text-center">
            <p className="text-muted-foreground text-sm">
              Search by restaurant address to unlock AI insights for this dish.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
