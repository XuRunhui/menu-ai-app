'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Upload, Globe } from 'lucide-react';
import AppHeader from '@/components/layout/AppHeader';
import UploadMenuPanel from '@/components/search/UploadMenuPanel';
import PlaceSearchPanel from '@/components/search/PlaceSearchPanel';
import { cn } from '@/lib/utils/cn';

function SearchContent() {
  const searchParams = useSearchParams();
  const mode = searchParams.get('mode') as 'upload' | 'places' | null;

  // For 'places' mode, user can toggle between auto-fetch and upload
  const [placesSubMode, setPlacesSubMode] = useState<'auto' | 'upload'>('auto');

  const isUploadMode = mode === 'upload' || (mode === 'places' && placesSubMode === 'upload');
  const isPlacesAutoMode = mode === 'places' && placesSubMode === 'auto';

  return (
    <main className="min-h-screen bg-background flex flex-col">
      <AppHeader showBack backHref="/" />

      <div className="flex-1 max-w-xl mx-auto w-full px-6 py-12">
        {/* Page header */}
        <div className="mb-10 opacity-0 animate-fade-slide-up stagger-1">
          <p className="text-xs font-medium tracking-widest uppercase text-primary/70 mb-3">
            {mode === 'upload' ? 'Upload Menu' : 'Search Restaurant'}
          </p>
          <h1 className="font-display text-4xl font-light text-foreground leading-tight">
            {mode === 'upload'
              ? 'Upload a menu image'
              : 'Find your restaurant'
            }
          </h1>
          <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
            {mode === 'upload'
              ? 'Take a photo of any restaurant menu — we\'ll parse and translate it instantly.'
              : 'Search by restaurant name, cuisine, or neighbourhood.'}
          </p>
        </div>

        {/* Sub-mode toggle for Places path */}
        {mode === 'places' && (
          <div className="mb-8 opacity-0 animate-fade-slide-up stagger-1">
            <div className="flex rounded-xl border border-border bg-muted p-1 gap-1">
              <button
                onClick={() => setPlacesSubMode('auto')}
                className={cn(
                  'flex-1 flex items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-medium transition-all duration-200',
                  placesSubMode === 'auto'
                    ? 'bg-card text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                <Globe className="w-4 h-4" />
                Auto Fetch Menu
              </button>
              <button
                onClick={() => setPlacesSubMode('upload')}
                className={cn(
                  'flex-1 flex items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-medium transition-all duration-200',
                  placesSubMode === 'upload'
                    ? 'bg-card text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                <Upload className="w-4 h-4" />
                Upload Menu Image
              </button>
            </div>
            <p className="mt-2 text-xs text-muted-foreground text-center">
              {placesSubMode === 'auto'
                ? 'We\'ll fetch the restaurant\'s popular dishes from Google Places & web reviews.'
                : 'Upload a photo of the physical menu at this restaurant.'}
            </p>
          </div>
        )}

        {/* Panel content */}
        {(mode === 'upload' || isUploadMode) && <UploadMenuPanel />}
        {isPlacesAutoMode && <PlaceSearchPanel />}
      </div>
    </main>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-background">
        <AppHeader showBack backHref="/" />
        <div className="max-w-xl mx-auto px-6 py-12 space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 rounded-xl bg-muted animate-pulse" />
          ))}
        </div>
      </main>
    }>
      <SearchContent />
    </Suspense>
  );
}
