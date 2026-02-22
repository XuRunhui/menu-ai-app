'use client';

import { useState, useMemo } from 'react';
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
  categories: { key: string; label: string }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin">
      {categories.map(({ key, label }) => (
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
        </button>
      ))}
    </div>
  );
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
  const { parsedMenu, popularDishes, checkIsRecommended, restaurant, targetLanguage } = useAppContext();
  // Pass restaurant name to DishCard so it can fetch per-dish images.
  // Undefined in upload-only flow — DishCard handles that gracefully.
  const restaurantName = restaurant?.name || undefined;
  const showTranslation = Boolean(targetLanguage);

  // Build category list based purely on available data.
  // Parsed menu (from image upload) always takes priority when present —
  // it's more complete than Google's auto-fetched popular dishes.
  // Popular dishes are used as fallback for the places-only flow.
  const categories: MenuCategory[] = useMemo(() => {
    if (parsedMenu?.menu && parsedMenu.menu.length > 0) {
      return parsedMenu.menu;
    }
    if (popularDishes.length > 0) {
      return [{
        category: 'Popular Dishes',
        items: popularDishes.map(popularDishToMenuItem),
      }];
    }
    return [];
  }, [parsedMenu, popularDishes]);

  // Each pill has a stable key (original name) and a display label (translated when available).
  const categoryEntries = categories.map((c) => ({
    key: c.category,
    label: (showTranslation && c.category_translated) ? c.category_translated : c.category,
  }));

  const [activeCategory, setActiveCategory] = useState(categories[0]?.category ?? '');

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
            onChange={setActiveCategory}
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
              isRecommended={checkIsRecommended(item.name)}
              restaurantName={restaurantName}
              showTranslation={showTranslation}
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
