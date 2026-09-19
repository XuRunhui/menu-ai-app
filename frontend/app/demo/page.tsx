'use client';

import { useRouter } from 'next/navigation';
import { ArrowRight, Check } from 'lucide-react';
import AppHeader from '@/components/layout/AppHeader';
import { Button } from '@/components/ui/button';
import { DEMO_STEPS, setDemoStep, type DemoStep } from '@/lib/demoTour';

/**
 * The tour's starting page: the three things Menuist does, each one click from running for real
 * on sample input. A bar at the bottom of each page then says what's on screen and what's next.
 */
export default function DemoPage() {
  const router = useRouter();

  const start = (step: DemoStep) => {
    setDemoStep(step.number);
    router.push(step.start);
  };

  return (
    <main className="min-h-screen bg-background flex flex-col">
      <AppHeader showBack backHref="/" />

      <div className="flex-1 max-w-3xl mx-auto w-full px-6 py-12">
        <div className="mb-10 opacity-0 animate-fade-slide-up stagger-1">
          <p className="text-xs font-medium tracking-widest uppercase text-primary/70 mb-3">Tour</p>
          <h1 className="font-display text-4xl font-light text-foreground leading-tight">
            Menuist in three steps
          </h1>
          <p className="text-muted-foreground mt-2 text-sm leading-relaxed max-w-xl">
            Each step runs the real thing on sample input, so you see exactly what you&apos;d get with your
            own menu or restaurant. A bar at the bottom of the page explains what you&apos;re looking at.
          </p>
        </div>

        <ol className="space-y-4">
          {DEMO_STEPS.map((step, index) => (
            <li
              key={step.number}
              className="opacity-0 animate-fade-slide-up rounded-2xl border border-border bg-card p-5 sm:p-6"
              style={{ animationDelay: `${0.1 + index * 0.08}s` }}
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="text-xs font-medium uppercase tracking-wider text-primary">Step {step.number}</p>
                  <h2 className="mt-1 font-display text-2xl font-light text-foreground">{step.title}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">{step.summary}</p>
                  <ul className="mt-3 space-y-1.5">
                    {step.shows.map((item) => (
                      <li key={item} className="flex items-start gap-2 text-sm text-foreground/85">
                        <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
                <Button
                  onClick={() => start(step)}
                  variant={index === 0 ? 'default' : 'outline'}
                  className="shrink-0 gap-1.5 self-start"
                >
                  {step.action}
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </li>
          ))}
        </ol>

        <p className="mt-8 text-xs text-muted-foreground/70">
          The sample menu opens instantly. Looking up a restaurant and asking the assistant use live
          Google and DeepSeek calls, and take a few seconds each.
        </p>
      </div>
    </main>
  );
}
