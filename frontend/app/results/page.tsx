'use client';

import { Suspense, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import AppHeader from '@/components/layout/AppHeader';
import ResultsHeader from '@/components/results/ResultsHeader';
import DishListTab from '@/components/results/DishListTab';
import ComboTab from '@/components/results/ComboTab';
import MenuSourcesPanel from '@/components/results/MenuSourcesPanel';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useAppContext } from '@/context/AppContext';
import { useAuth } from '@/context/AuthContext';
import { useSessionRestore } from '@/hooks/useSessionRestore';

export default function ResultsPage() {
  // useSearchParams (in useSessionRestore) needs a Suspense boundary.
  return (
    <Suspense>
      <ResultsContent />
    </Suspense>
  );
}

function GuestNotice() {
  const { authEnabled, user, loading } = useAuth();
  if (loading || !authEnabled || user) return null;
  return (
    <div className="border-b border-border bg-accent/60">
      <p className="max-w-5xl mx-auto px-6 py-2.5 text-xs text-muted-foreground">
        You&apos;re browsing as a guest, so these results disappear when you refresh.{' '}
        <Link href="/login?next=/search?mode=upload" className="text-primary hover:underline">Sign in</Link>{' '}
        to save menus and restaurants to your history.
      </p>
    </div>
  );
}

function ResultsContent() {
  const router = useRouter();
  const restore = useSessionRestore();
  const { parsedMenu, placeDetails, openedFrom } = useAppContext();

  // Back goes where the results came from: the assistant's conversation, the upload page, or the
  // places search.
  const backHref =
    openedFrom === 'assistant' ? '/assistant' : parsedMenu ? '/search?mode=upload' : '/search?mode=places';

  // Nothing to show and nothing to restore (e.g. a guest refreshed the page): go home.
  useEffect(() => {
    if (restore === 'unavailable') {
      router.replace('/');
    }
  }, [restore, router]);

  if (restore !== 'ready' || (!parsedMenu && !placeDetails)) {
    return (
      <main className="min-h-screen bg-background flex flex-col">
        <AppHeader showBack backHref="/" />
        <p className="text-center text-sm text-muted-foreground py-24">Loading your saved results…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background flex flex-col">
      <AppHeader showBack backHref={backHref} />

      <GuestNotice />
      <ResultsHeader />

      {/* A restaurant from Google: build its menu from every source. An uploaded menu needs none. */}
      {placeDetails && !parsedMenu && (
        <div className="max-w-5xl mx-auto w-full px-6 pt-6 opacity-0 animate-fade-slide-up stagger-2">
          <MenuSourcesPanel />
        </div>
      )}

      <div className="flex-1 max-w-5xl mx-auto w-full px-6 py-8">
        <Tabs defaultValue="dishes" className="opacity-0 animate-fade-slide-up stagger-3">
          <TabsList className="mb-8 bg-muted/80 border border-border/60">
            <TabsTrigger value="dishes" className="px-6">
              Dish List
            </TabsTrigger>
            <TabsTrigger value="combo" className="px-6">
              Combo Recommendations
            </TabsTrigger>
          </TabsList>

          <TabsContent value="dishes">
            <DishListTab />
          </TabsContent>

          <TabsContent value="combo">
            <ComboTab />
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}
