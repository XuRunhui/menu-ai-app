'use client';

import { MapPin, Star, Globe, Phone, Loader2 } from 'lucide-react';
import { useAppContext } from '@/context/AppContext';

function PriceLevel({ level }: { level?: number }) {
  if (!level) return null;
  return (
    <span className="text-sm text-muted-foreground">
      {'$'.repeat(level)}
    </span>
  );
}

export default function ResultsHeader() {
  const { restaurant, knowledgeBaseStatus, parsedMenu, entryMode } = useAppContext();

  if (!restaurant?.name) {
    return (
      <div className="border-b border-border bg-background px-6 py-6 opacity-0 animate-fade-slide-up stagger-2">
        <div className="max-w-5xl mx-auto">
          <p className="text-xs font-medium tracking-widest uppercase text-primary/70 mb-1">Menu</p>
          <h2 className="font-display text-3xl font-light text-foreground">
            {parsedMenu?.detected_language
              ? `${parsedMenu.detected_language} Menu`
              : 'Parsed Menu'}
          </h2>
          {parsedMenu?.target_language && (
            <p className="text-sm text-muted-foreground mt-1">
              Translated to {parsedMenu.target_language}
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="border-b border-border bg-background px-6 py-6 opacity-0 animate-fade-slide-up stagger-2">
      <div className="max-w-5xl mx-auto">
        <p className="text-xs font-medium tracking-widest uppercase text-primary/70 mb-1">Restaurant</p>

        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-display text-3xl font-light text-foreground leading-tight">
              {restaurant.name}
            </h2>

            <div className="flex items-center gap-4 mt-2 flex-wrap">
              {restaurant.rating && (
                <span className="flex items-center gap-1.5 text-sm">
                  <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
                  <span className="font-medium">{restaurant.rating.toFixed(1)}</span>
                  {restaurant.user_ratings_total && (
                    <span className="text-muted-foreground">
                      ({restaurant.user_ratings_total.toLocaleString()})
                    </span>
                  )}
                </span>
              )}

              <PriceLevel level={restaurant.price_level} />

              {restaurant.location && (
                <span className="flex items-center gap-1 text-sm text-muted-foreground">
                  <MapPin className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate max-w-xs">{restaurant.location}</span>
                </span>
              )}
            </div>

            <div className="flex items-center gap-3 mt-2 flex-wrap">
              {restaurant.website && (
                <a
                  href={restaurant.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  <Globe className="w-3 h-3" />
                  Website
                </a>
              )}
              {restaurant.formatted_phone_number && (
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Phone className="w-3 h-3" />
                  {restaurant.formatted_phone_number}
                </span>
              )}
            </div>
          </div>

          {/* KB status indicator */}
          {knowledgeBaseStatus === 'building' && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted px-3 py-2 rounded-lg shrink-0">
              <Loader2 className="w-3 h-3 animate-spin" />
              Loading AI insights…
            </div>
          )}
          {knowledgeBaseStatus === 'ready' && entryMode === 'places' && (
            <div className="flex items-center gap-2 text-xs text-primary bg-primary/10 px-3 py-2 rounded-lg shrink-0">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />
              AI insights ready
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
