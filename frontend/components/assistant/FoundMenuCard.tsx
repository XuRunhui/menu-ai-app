'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { BookOpen, ChevronRight, Loader2 } from 'lucide-react';
import { getPlaceDetails, type FoundMenu, type SourceResult } from '@/lib/api';
import { useAppContext } from '@/context/AppContext';
import { rememberRestaurant } from '@/lib/localHistory';

const SOURCE_NAMES: Record<string, string> = {
  website: 'its website',
};

function describeSources(results: SourceResult[]): string {
  const found = results.filter((r) => r.report.status === 'found').map((r) => SOURCE_NAMES[r.report.kind]);
  return found.length ? `From ${found.join(' and ')}` : 'From reviews';
}

/**
 * The menu the assistant assembled, opened in the full results view with every source labelled.
 *
 * The chat already paid for reading the website, so its result is handed to the results page as
 * it is instead of being fetched again. The diner can add a photo of the
 * menu there, and it is merged with what the assistant found.
 */
export default function FoundMenuCard({ found }: { found: FoundMenu }) {
  const router = useRouter();
  const { openPlace } = useAppContext();
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = async () => {
    setOpening(true);
    setError(null);
    try {
      const details = await getPlaceDetails(found.place_id, found.restaurant_name);
      openPlace(details, {
        from: 'assistant',
        menuSources: {
          placeId: found.place_id,
          website: found.results.find((r) => r.report.kind === 'website'),
          uploads: [],
          combined: found.combined,
        },
      });
      rememberRestaurant({ placeId: found.place_id, label: found.restaurant_name });
      router.push(`/results?place=${encodeURIComponent(found.place_id)}`);
    } catch {
      setError('Could not open the menu. Please try again.');
      setOpening(false);
    }
  };

  return (
    <button
      onClick={open}
      disabled={opening}
      className="w-full text-left rounded-xl border border-border bg-card p-4 transition-all duration-200
                 hover:border-primary/40 hover:shadow-sm disabled:cursor-wait disabled:opacity-70"
    >
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
          {opening ? <Loader2 className="h-4 w-4 animate-spin" /> : <BookOpen className="h-4 w-4" strokeWidth={1.5} />}
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-medium text-foreground">
            {found.restaurant_name || 'Menu'} — {found.combined.total_items} dishes
          </p>
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
            {describeSources(found.results)}. Every dish is labelled with where it came from, and you
            can add a photo of the menu to fill any gaps.
          </p>
          <span className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary">
            Open the menu
            <ChevronRight className="h-3 w-3" />
          </span>
          {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
        </div>
      </div>
    </button>
  );
}
