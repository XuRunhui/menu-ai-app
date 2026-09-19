'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Search, MapPin, Star, Loader2, ChevronRight, Building2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils/cn';
import { searchPlaces, getPlaceDetails, type GooglePlace } from '@/lib/api';
import { useAppContext } from '@/context/AppContext';
import { rememberRestaurant } from '@/lib/localHistory';
import { DEMO_RESTAURANT_QUERY } from '@/lib/demoTour';

function StarRating({ rating }: { rating?: number }) {
  if (!rating) return null;
  return (
    <span className="flex items-center gap-1 text-xs text-muted-foreground">
      <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
      <span className="font-medium text-foreground">{rating.toFixed(1)}</span>
    </span>
  );
}

function PriceLevel({ level }: { level?: number }) {
  if (!level) return null;
  return (
    <span className="text-xs text-muted-foreground font-medium">
      {'$'.repeat(level)}{'$'.repeat(Math.max(0, 4 - level)).replace(/\$/g, '·')}
    </span>
  );
}

export default function PlaceSearchPanel() {
  const router = useRouter();
  const { openPlace } = useAppContext();
  // The tour's second step lands here with ?demo=2 and searches for its sample restaurant.
  const searchParams = useSearchParams();
  const fromTour = searchParams.get('demo') === '2';

  const [query, setQuery] = useState(fromTour ? DEMO_RESTAURANT_QUERY : '');
  const [results, setResults] = useState<GooglePlace[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (text: string = query) => {
    if (!text.trim()) return;
    setIsSearching(true);
    setError(null);
    setResults([]);
    setHasSearched(true);

    try {
      const data = await searchPlaces(text.trim());
      setResults(data.results ?? []);
      if ((data.results ?? []).length === 0) {
        setError(
          data.status && data.status !== 'ZERO_RESULTS' && data.status !== 'OK'
            ? `Search is unavailable right now (Google: ${data.status}).`
            : 'No restaurants found. Try a different search term.'
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed. Please try again.');
    } finally {
      setIsSearching(false);
    }
  };

  const tourSearched = useRef(false);
  useEffect(() => {
    if (!fromTour || tourSearched.current) return;
    tourSearched.current = true;
    router.replace('/search?mode=places'); // Back or a refresh shouldn't search again
    queueMicrotask(() => void handleSearch(DEMO_RESTAURANT_QUERY));
    // Runs once, on arrival from the tour.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fromTour]);

  const handleSelect = async (place: GooglePlace) => {
    setSelectedId(place.place_id);
    setIsSelecting(true);
    setError(null);

    try {
      const details = await getPlaceDetails(place.place_id, query.trim());
      openPlace(details);

      rememberRestaurant({ placeId: place.place_id, label: place.name });
      router.push(`/results?place=${encodeURIComponent(place.place_id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load restaurant details.');
      setIsSelecting(false);
      setSelectedId(null);
    }
  };

  return (
    <div className="space-y-5 opacity-0 animate-fade-slide-up stagger-2">
      {/* Search bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <Input
            placeholder="e.g. Tofu House Koreatown LA"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="pl-9"
          />
        </div>
        <Button
          onClick={() => handleSearch()}
          disabled={isSearching || !query.trim()}
          className="shrink-0 gap-1.5"
        >
          {isSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
          Search
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Loading shimmer */}
      {isSearching && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 rounded-xl bg-muted animate-pulse" />
          ))}
        </div>
      )}

      {/* Results */}
      {!isSearching && results.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            {results.length} result{results.length !== 1 ? 's' : ''} found
          </p>
          {results.map((place) => (
            <button
              key={place.place_id}
              onClick={() => handleSelect(place)}
              disabled={isSelecting}
              className={cn(
                'w-full text-left rounded-xl border border-border bg-card p-4',
                'flex items-start gap-4 transition-all duration-200',
                'hover:border-primary/40 hover:shadow-sm hover:bg-accent/30',
                'disabled:opacity-70 disabled:cursor-not-allowed',
                selectedId === place.place_id && 'border-primary/60 bg-accent/50',
              )}
            >
              <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-muted shrink-0">
                {selectedId === place.place_id && isSelecting
                  ? <Loader2 className="w-4 h-4 animate-spin text-primary" />
                  : <Building2 className="w-4 h-4 text-muted-foreground" />
                }
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-medium text-foreground truncate">{place.name}</p>
                  <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
                </div>

                <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1 truncate">
                  <MapPin className="w-3 h-3 shrink-0" />
                  <span className="truncate">{place.formatted_address}</span>
                </p>

                <div className="flex items-center gap-3 mt-1.5">
                  <StarRating rating={place.rating} />
                  {place.user_ratings_total && (
                    <span className="text-xs text-muted-foreground">
                      {place.user_ratings_total.toLocaleString()} reviews
                    </span>
                  )}
                  <PriceLevel level={place.price_level} />
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Empty state after search */}
      {!isSearching && hasSearched && results.length === 0 && !error && (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <Search className="w-8 h-8 text-muted-foreground/50" />
          <p className="text-muted-foreground text-sm">No restaurants found for this search.</p>
        </div>
      )}
    </div>
  );
}
