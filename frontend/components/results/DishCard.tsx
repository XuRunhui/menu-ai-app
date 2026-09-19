'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Star } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { getDishImage, knownDishImage } from '@/lib/api';
import { useAppContext } from '@/context/AppContext';
import type { AltPrice, MenuItem, MenuSourceKind } from '@/lib/types';

interface DishCardProps {
  item: MenuItem;
  isRecommended: boolean;
  restaurantName?: string;  // needed to trigger image fetch; omit for upload-only flow
  showTranslation?: boolean;
  /** The description is a reviewer's words, not the menu's: shown, but not used to find the photo. */
  descriptionIsQuote?: boolean;
  className?: string;
}

function formatPrice(item: MenuItem): string | null {
  if (item.price_original) return item.price_original;
  if (item.price != null) {
    const symbol = item.currency ?? '$';
    return `${symbol}${item.price.toFixed(2)}`;
  }
  return null;
}

const SOURCE_BADGES: Record<MenuSourceKind, { label: string; className: string }> = {
  upload: { label: 'Your photo', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  website: { label: 'Website', className: 'bg-sky-50 text-sky-700 border-sky-200' },
  reviews: { label: 'Reviews', className: 'bg-amber-50 text-amber-700 border-amber-200' },
};

function formatAltPrice(alt: AltPrice): string | null {
  if (alt.price_original) return alt.price_original;
  return alt.price != null ? `${alt.currency ?? '$'}${alt.price.toFixed(2)}` : null;
}

// Deterministic pastel gradient from dish name (fallback when no image)
function getDishGradient(name: string): string {
  const gradients = [
    'from-amber-50 to-orange-50',
    'from-rose-50 to-pink-50',
    'from-emerald-50 to-teal-50',
    'from-sky-50 to-blue-50',
    'from-violet-50 to-purple-50',
    'from-lime-50 to-green-50',
    'from-orange-50 to-amber-50',
    'from-cyan-50 to-sky-50',
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i);
    hash |= 0;
  }
  return gradients[Math.abs(hash) % gradients.length];
}

export default function DishCard({
  item,
  isRecommended,
  restaurantName,
  showTranslation = false,
  descriptionIsQuote = false,
  className,
}: DishCardProps) {
  const { resultsQuery } = useAppContext();
  // A card mounts again whenever its category is reopened; start from the photo already found.
  const [imageUrl, setImageUrl] = useState<string | null>(
    () => knownDishImage(item.name, restaurantName)?.image_url ?? null
  );
  const [imageCredit, setImageCredit] = useState(() => knownDishImage(item.name, restaurantName)?.attribution ?? '');
  const [imageLoaded, setImageLoaded] = useState(false);

  // With a translation on, show the translated text first and keep the original underneath —
  // unless the "translation" only changes capitals ("Japchae" / "japchae").
  const same = (a?: string | null, b?: string | null) =>
    (a ?? '').trim().toLowerCase() === (b ?? '').trim().toLowerCase();
  const translatedName = showTranslation && !same(item.name_translated, item.name) ? item.name_translated : null;
  const displayName = translatedName ?? item.name;
  const originalName = translatedName ? item.name : null;
  const translatedDescription =
    showTranslation && !same(item.description_translated, item.description) ? item.description_translated : null;
  const displayDescription = translatedDescription ?? item.description;
  const originalDescription = translatedDescription ? item.description : null;
  const price = formatPrice(item);
  const encodedName = encodeURIComponent(item.name);
  // Only combined menus carry sources; a single uploaded menu shows no badges.
  const sources = item.sources ?? [];
  const altPrices = (item.alt_prices ?? [])
    .map((alt) => ({ source: SOURCE_BADGES[alt.source]?.label ?? alt.source, price: formatAltPrice(alt) }))
    .filter((alt) => alt.price);

  // Lazy-fetch dish image from backend (search, judge, then its cache); asked once per visit.
  // restaurantName is optional — when absent the backend searches by dish name alone.
  useEffect(() => {
    let cancelled = false;

    getDishImage(item.name, restaurantName, {
      translatedName: item.name_translated,
      // The judge is told "the menu describes it as …"; a review quote there misleads it.
      description: descriptionIsQuote ? null : item.description_translated || item.description,
    })
      .then((data) => {
        if (!cancelled && data.image_url) {
          setImageUrl(data.image_url);
          setImageCredit(data.attribution ?? '');
        }
      })
      .catch(() => {}); // silently fail — placeholder stays visible

    return () => { cancelled = true; };
  }, [item.name, restaurantName]);

  return (
    <Link href={`/dish/${encodedName}${resultsQuery}`} className={cn('block group', className)}>
      <div className={cn(
        'rounded-2xl border border-border bg-card overflow-hidden',
        'transition-all duration-300 ease-out',
        'hover:border-primary/30 hover:shadow-[0_8px_24px_rgba(184,92,56,0.09)] hover:-translate-y-1',
      )}>
        {/* Image area — 4:3 ratio */}
        <div className="aspect-[4/3] relative overflow-hidden bg-muted">
          {/* Gradient placeholder — always rendered underneath */}
          <div className={cn(
            'absolute inset-0 bg-gradient-to-br flex items-center justify-center',
            getDishGradient(item.name),
            imageLoaded && 'opacity-0',
          )}>
            <span className="font-display text-5xl font-light text-foreground/20 select-none">
              {item.name.charAt(0).toUpperCase()}
            </span>
          </div>

          {/* Actual image — fades in once loaded */}
          {imageUrl && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={imageUrl}
              alt={item.name}
              title={imageCredit ? `Photo: ${imageCredit}` : item.name}
              onLoad={() => setImageLoaded(true)}
              onError={() => setImageUrl(null)}
              className={cn(
                'absolute inset-0 w-full h-full object-cover transition-opacity duration-500',
                imageLoaded ? 'opacity-100' : 'opacity-0',
              )}
            />
          )}

          {/* Recommended badge */}
          {isRecommended && (
            <div className="absolute top-2.5 right-2.5 flex items-center gap-1 bg-primary text-primary-foreground text-xs font-medium px-2 py-1 rounded-full shadow-sm z-10">
              <Star className="w-3 h-3 fill-current" />
              <span>Popular</span>
            </div>
          )}
        </div>

        {/* Info area */}
        <div className="p-3.5">
          <div className="flex items-start justify-between gap-2">
            <h4 className={cn(
              'text-sm font-medium text-foreground leading-snug line-clamp-2',
              'group-hover:text-primary transition-colors duration-200',
            )}>
              {isRecommended && (
                <Star className="inline w-3 h-3 fill-amber-400 text-amber-400 mr-1 mb-0.5" />
              )}
              {displayName}
            </h4>

            {price && (
              <span className="text-xs text-muted-foreground font-medium shrink-0 mt-0.5">
                {price}
              </span>
            )}
          </div>

          {originalName && (
            <p className="text-xs text-muted-foreground/80 mt-0.5 line-clamp-1">{originalName}</p>
          )}

          {displayDescription && (
            <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2 leading-relaxed">
              {displayDescription}
            </p>
          )}

          {originalDescription && (
            <p className="text-xs text-muted-foreground/70 mt-1 line-clamp-2 leading-relaxed">
              {originalDescription}
            </p>
          )}

          {altPrices.length > 0 && (
            // Sources disagreeing on a price is usually the first sign one of them is out of date.
            <p
              className="text-[11px] text-amber-700 mt-1.5"
              title="Prices differ between sources — the menu may have changed"
            >
              {altPrices.map((alt) => `${alt.source}: ${alt.price}`).join(' · ')}
            </p>
          )}

          {sources.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {sources.map((source) => (
                <span
                  key={source}
                  className={cn(
                    'rounded-full border px-1.5 py-px text-[10px] font-medium leading-4',
                    SOURCE_BADGES[source]?.className ?? 'bg-muted text-muted-foreground border-border'
                  )}
                >
                  {SOURCE_BADGES[source]?.label ?? source}
                  {source === 'reviews' && (item.review_mentions ?? 0) > 1 ? ` ×${item.review_mentions}` : ''}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
