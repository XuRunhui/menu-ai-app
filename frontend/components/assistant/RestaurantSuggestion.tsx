'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, MapPin, Star, Navigation } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { getPlaceDetails, type AssistantRestaurant } from '@/lib/api';
import { useAppContext } from '@/context/AppContext';
import { rememberRestaurant } from '@/lib/localHistory';

/**
 * A restaurant the assistant found. Opening one runs the same flow as the search page, so the
 * conversation hands off into the menu and dish views the rest of the app already provides.
 */
export default function RestaurantSuggestion({ place }: { place: AssistantRestaurant }) {
  const router = useRouter();
  const { openPlace } = useAppContext();
  const [isOpening, setIsOpening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = async () => {
    setIsOpening(true);
    setError(null);
    try {
      const details = await getPlaceDetails(place.place_id, place.name);
      openPlace(details, { from: 'assistant' });
      rememberRestaurant({ placeId: place.place_id, label: place.name });

      router.push(`/results?place=${encodeURIComponent(place.place_id)}`);
    } catch {
      setError('Could not open that restaurant. Try another one.');
      setIsOpening(false);
    }
  };

  return (
    <button
      onClick={open}
      disabled={isOpening}
      className={cn(
        'w-full text-left rounded-xl border border-border bg-card p-4',
        'transition-all duration-200 hover:border-primary/40 hover:shadow-sm',
        'disabled:opacity-60 disabled:cursor-wait'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-foreground truncate">{place.name}</p>
          {place.address && (
            <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground truncate">
              <MapPin className="w-3 h-3 shrink-0" />
              {place.address}
            </p>
          )}
        </div>
        {isOpening && <Loader2 className="w-4 h-4 shrink-0 animate-spin text-primary" />}
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {place.rating != null && (
          <span className="flex items-center gap-1">
            <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
            <span className="font-medium text-foreground">{place.rating.toFixed(1)}</span>
            {place.user_ratings_total != null && <span>({place.user_ratings_total})</span>}
          </span>
        )}
        {place.distance_km != null && (
          <span className="flex items-center gap-1">
            <Navigation className="w-3 h-3" />
            {place.distance_km < 1
              ? `${Math.round(place.distance_km * 1000)} m`
              : `${place.distance_km} km`}
          </span>
        )}
        {place.price_level != null && place.price_level > 0 && (
          <span className="font-medium">{'$'.repeat(place.price_level)}</span>
        )}
        {place.open_now != null && (
          <span className={place.open_now ? 'text-emerald-600' : 'text-muted-foreground'}>
            {place.open_now ? 'Open now' : 'Closed'}
          </span>
        )}
      </div>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </button>
  );
}
