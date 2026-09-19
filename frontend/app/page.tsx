'use client';

import { Upload, MapPin, Sparkles, PlayCircle } from 'lucide-react';
import EntryCard from '@/components/home/EntryCard';
import UserMenu from '@/components/layout/UserMenu';
import { useAppContext } from '@/context/AppContext';
import { useRouter } from 'next/navigation';

export default function HomePage() {
  const { setEntryMode } = useAppContext();
  const router = useRouter();

  const handleUpload = () => {
    setEntryMode('upload');
    router.push('/search?mode=upload');
  };

  const handleSearch = () => {
    setEntryMode('places');
    router.push('/search?mode=places');
  };

  const handleAssistant = () => {
    router.push('/assistant');
  };

  return (
    <main className="min-h-screen bg-background flex flex-col">
      {/* Decorative top border line */}
      <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-primary/40 to-transparent" />

      <div className="w-full max-w-5xl mx-auto px-6 pt-4 flex justify-end">
        <UserMenu />
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-6 py-20">
        {/* Header */}
        <div className="text-center mb-16 space-y-4 opacity-0 animate-fade-slide-up stagger-1">
          <div className="inline-flex items-center gap-2 text-xs font-medium tracking-widest uppercase text-primary/70 mb-2">
            <span className="h-px w-6 bg-primary/40" />
            <span>AI-Powered Dining Guide</span>
            <span className="h-px w-6 bg-primary/40" />
          </div>
          <h1 className="font-display text-6xl md:text-7xl font-light text-foreground tracking-tight leading-none">
            Menuist
          </h1>
          <p className="text-muted-foreground text-lg font-light max-w-md mx-auto leading-relaxed">
            Parse any menu, discover dishes, and get personalized recommendations from restaurant reviews.
          </p>
          <button
            onClick={() => router.push('/demo')}
            className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/5 px-4 py-2
                       text-sm font-medium text-primary transition-colors hover:bg-primary/10"
          >
            <PlayCircle className="h-4 w-4" />
            Take the tour: see each part in action
          </button>
        </div>

        {/* Cards grid */}
        <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="opacity-0 animate-fade-slide-up stagger-2">
            <EntryCard
              icon={Upload}
              title="Upload Menu"
              description="Photograph any menu and get instant AI parsing with translation in 12+ languages."
              onClick={handleUpload}
            />
          </div>

          <div className="opacity-0 animate-fade-slide-up stagger-3">
            <EntryCard
              icon={MapPin}
              title="Search Restaurant"
              description="Find a restaurant by name or address to explore its menu and popular dishes."
              onClick={handleSearch}
            />
          </div>

          <div className="opacity-0 animate-fade-slide-up stagger-4">
            <EntryCard
              icon={Sparkles}
              title="AI Assistant"
              description="Tell it what you feel like and how far you'll travel — it finds the restaurant and what to order."
              onClick={handleAssistant}
            />
          </div>
        </div>

        {/* Footer note */}
        <p className="mt-16 text-xs text-muted-foreground/60 opacity-0 animate-fade-slide-up stagger-5">
          Powered by DeepSeek · Google Places · FlavorGraph ingredient pairings
        </p>
      </div>

      {/* Decorative bottom border */}
      <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-border to-transparent" />
    </main>
  );
}
