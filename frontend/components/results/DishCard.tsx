'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Star } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { getDishImage } from '@/lib/api';
import type { MenuItem } from '@/lib/types';

interface DishCardProps {
  item: MenuItem;
  isRecommended: boolean;
  restaurantName?: string;  // needed to trigger image fetch; omit for upload-only flow
  showTranslation?: boolean;
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
  className,
}: DishCardProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageLoaded, setImageLoaded] = useState(false);

  const displayName = (showTranslation && item.name_translated) ? item.name_translated : item.name;
  const price = formatPrice(item);
  const encodedName = encodeURIComponent(item.name);

  // Lazy-fetch dish image from backend (DDGS search + local cache).
  // restaurantName is optional — when absent the backend searches by dish name alone.
  useEffect(() => {
    let cancelled = false;

    getDishImage(item.name, restaurantName)
      .then((data) => {
        if (!cancelled && data.image_url) {
          setImageUrl(data.image_url);
        }
      })
      .catch(() => {}); // silently fail — placeholder stays visible

    return () => { cancelled = true; };
  }, [item.name, restaurantName]);

  return (
    <Link href={`/dish/${encodedName}`} className={cn('block group', className)}>
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
              onLoad={() => setImageLoaded(true)}
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

          {(item.description || item.description_translated) && (
            <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2 leading-relaxed">
              {(showTranslation && item.description_translated) ? item.description_translated : item.description}
            </p>
          )}
        </div>
      </div>
    </Link>
  );
}
