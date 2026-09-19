'use client';

import { Suspense } from 'react';
import AppHeader from '@/components/layout/AppHeader';
import ChatPanel from '@/components/assistant/ChatPanel';

export default function AssistantPage() {
  return (
    <main className="min-h-screen bg-background flex flex-col">
      <AppHeader showBack backHref="/" />

      <div className="flex-1 max-w-2xl mx-auto w-full px-6 py-8">
        <div className="mb-6 opacity-0 animate-fade-slide-up stagger-1">
          <p className="text-xs font-medium tracking-widest uppercase text-primary/70 mb-3">
            AI Assistant
          </p>
          <h1 className="font-display text-4xl font-light text-foreground leading-tight">
            What are you eating tonight?
          </h1>
          <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
            Tell me what you feel like, where you are, and how far you&apos;ll go. I&apos;ll find
            somewhere real and tell you what to order.
          </p>
        </div>

        <div className="opacity-0 animate-fade-slide-up stagger-2">
          {/* ChatPanel reads ?demo= (the tour), which needs a Suspense boundary. */}
          <Suspense>
            <ChatPanel />
          </Suspense>
        </div>
      </div>
    </main>
  );
}
