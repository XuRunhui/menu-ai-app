'use client';

import { useMemo, useState } from 'react';
import { useAppContext } from '@/context/AppContext';
import DishCard from './DishCard';
import type { MenuCategory, MenuItem } from '@/lib/types';
import type { PopularDish } from '@/lib/api';
import { cn } from '@/lib/utils/cn';

function CategoryPills({
  categories,
  active,
  onChange,
}: {
  categories: { key: string; label: string | null; original?: string | null }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin">
      {categories.map(({ key, label, original }) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={cn(
            'shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-all duration-200',
            active === key
              ? 'bg-foreground text-background'
              : 'bg-muted text-muted-foreground hover:bg-secondary hover:text-foreground'
          )}
        >
          {label}
          {original && <span className="ml-1.5 opacity-60">· {original}</span>}
        </button>
      ))}
    </div>
  );
}

/** Whether a translation says something the original doesn't (not just different capitals). */
function differs(translated: string | null | undefined, original: string): translated is string {
  return Boolean(translated) && translated!.trim().toLowerCase() !== original.trim().toLowerCase();
}

// Convert PopularDish to MenuItem-like shape for unified rendering
function popularDishToMenuItem(dish: PopularDish): MenuItem {
  return {
    name: dish.name,
    description: dish.sample_reviews?.[0] ?? null,
    price: null,
    price_original: null,
    currency: null,
  };
}

export default function DishListTab() {
  const { parsedMenu, popularDishes, checkIsRecommended, restaurant, targetLanguage, placeDetails, menuSources } =
    useAppContext();
  // Pass restaurant name to DishCard so it can fetch per-dish images.
  // Undefined in upload-only flow — DishCard handles that gracefully.
  const restaurantName = restaurant?.name || undefined;
  const combined =
    menuSources && menuSources.placeId === placeDetails?.place?.place_id ? menuSources.combined : null;
  // Combined menus are read into one language, so show translations wherever a dish has one.
  const showTranslation = Boolean(targetLanguage) || Boolean(combined);

  // An uploaded menu is shown as it is. A restaurant from Google shows the menu combined from
  // every source (see MenuSourcesPanel); review dishes alone are only the fallback before that.
  const fromReviews = !(parsedMenu?.menu?.length || combined?.menu.menu.length) && popularDishes.length > 0;
  const categories: MenuCategory[] = useMemo(() => {
    if (parsedMenu?.menu && parsedMenu.menu.length > 0) {
      return parsedMenu.menu;
    }
    if (combined && combined.menu.menu.length > 0) {
      return combined.menu.menu;
    }
    if (popularDishes.length > 0) {
      return [{
        category: 'Popular Dishes',
        items: popularDishes.map(popularDishToMenuItem),
      }];
    }
    return [];
  }, [parsedMenu, combined, popularDishes]);

  // Each pill has a stable key (original name), the translated label, and the original alongside it.
  const categoryEntries = categories.map((c) => {
    const translated =
      showTranslation && differs(c.category_translated, c.category) ? c.category_translated : null;
    return { key: c.category, label: translated ?? c.category, original: translated ? c.category : null };
  });

  // Sources arrive one after another, so the categories change under the page. Follow the first
  // category until the diner picks one, and never sit on a category that has disappeared.
  const [picked, setPicked] = useState<string | null>(null);
  const activeCategory =
    picked !== null && categories.some((c) => c.category === picked) ? picked : (categories[0]?.category ?? '');

  const activeItems = useMemo(() => {
    return categories.find((c) => c.category === activeCategory)?.items ?? [];
  }, [categories, activeCategory]);

  if (categories.length === 0) {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <p className="text-muted-foreground">No menu data available.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Category pill tabs */}
      {categoryEntries.length > 1 && (
        <div className="opacity-0 animate-fade-slide-up stagger-1">
          <CategoryPills
            categories={categoryEntries}
            active={activeCategory}
            onChange={setPicked}
          />
        </div>
      )}

      {/* Dish card grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
        {activeItems.map((item, idx) => (
          <div
            key={`${item.name}-${idx}`}
            className="opacity-0 animate-fade-slide-up"
            style={{ animationDelay: `${0.05 + idx * 0.04}s` }}
          >
            <DishCard
              item={item}
              // A combined menu's labels come from the server's match against the reviews, so the
              // star and the "Reviews" badge can never disagree. Single uploads use the local matcher.
              isRecommended={
                item.sources?.length ? item.sources.includes('reviews') : checkIsRecommended(item.name)
              }
              restaurantName={restaurantName}
              showTranslation={showTranslation}
              descriptionIsQuote={fromReviews}
            />
          </div>
        ))}
      </div>

      {activeItems.length === 0 && (
        <p className="text-center text-muted-foreground text-sm py-10">
          No dishes in this category.
        </p>
      )}
    </div>
  );
}
