'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AppHeader from '@/components/layout/AppHeader';
import ResultsHeader from '@/components/results/ResultsHeader';
import DishListTab from '@/components/results/DishListTab';
import ComboPlaceholder from '@/components/results/ComboPlaceholder';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useAppContext } from '@/context/AppContext';

export default function ResultsPage() {
  const router = useRouter();
  const { parsedMenu, placeDetails } = useAppContext();

  // Back destination: if we have a parsed menu (image upload flow), go back to the upload page.
  // If only place details are present, go back to the places search page.
  const backHref = parsedMenu ? '/search?mode=upload' : '/search?mode=places';

  // Guard: redirect home if no data
  useEffect(() => {
    if (!parsedMenu && !placeDetails) {
      router.replace('/');
    }
  }, [parsedMenu, placeDetails, router]);

  if (!parsedMenu && !placeDetails) {
    return null; // Will redirect
  }

  return (
    <main className="min-h-screen bg-background flex flex-col">
      <AppHeader showBack backHref={backHref} />

      <ResultsHeader />

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
            <ComboPlaceholder />
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}
