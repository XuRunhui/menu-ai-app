'use client';

import { Upload, MapPin, Sparkles } from 'lucide-react';
import EntryCard from '@/components/home/EntryCard';
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

  return (
    <main className="min-h-screen bg-background flex flex-col">
      {/* Decorative top border line */}
      <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-primary/40 to-transparent" />

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
              description="Get a personalized dining experience powered by conversational AI recommendations."
              disabled
            />
          </div>
        </div>

        {/* Footer note */}
        <p className="mt-16 text-xs text-muted-foreground/60 opacity-0 animate-fade-slide-up stagger-5">
          Powered by Gemini Vision · Google Places · RAG recommendations
        </p>
      </div>

      {/* Decorative bottom border */}
      <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-border to-transparent" />
    </main>
  );
}
