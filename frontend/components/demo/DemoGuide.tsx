'use client';

import { usePathname, useRouter } from 'next/navigation';
import { ArrowRight, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';
import { DEMO_RESTAURANT_QUERY, DEMO_STEPS, setDemoStep, useDemoStep } from '@/lib/demoTour';

const DISH_PAGE =
  'One dish up close: what the menu says about it, how it tastes, and what reviewers said, when any mention it.';

/** What the visitor is looking at, for the step they're on and the page they're on. */
function describe(step: number, pathname: string): string | null {
  const page = pathname.startsWith('/dish/') ? 'dish' : pathname;
  if (page === 'dish') return DISH_PAGE;
  switch (`${step} ${page}`) {
    case '1 /search':
      return 'Reading the sample menu: a photo of the menu at The Kroft…';
    case '1 /results':
      return 'This menu came from one photo: dishes by category with prices, and a photo found for each. Switch categories, open a dish, or try the Combo tab.';
    case '2 /search':
      return `Searching Google for ${DEMO_RESTAURANT_QUERY}. Pick it from the results to see its menu.`;
    case '2 /results':
      return 'This menu was put together from the restaurant’s website and its Google reviews, and every dish says where it came from. A photo of the menu can fill any gaps.';
    case '3 /assistant':
      return 'The assistant is finding spicy, affordable food near Koreatown. Open one of its suggestions.';
    case '3 /results':
      return 'Opened by the assistant, with its menu put together the same way. Back returns to the conversation.';
    default:
      return null;
  }
}

/**
 * The guided tour's bar along the bottom of the page: what's on screen, and the next step.
 * Rendered once in the root layout; shows only while a tour is in progress.
 */
export default function DemoGuide() {
  const step = useDemoStep();
  const pathname = usePathname();
  const router = useRouter();

  // The tour page explains every step itself.
  if (!step || pathname === '/demo') return null;

  const current = DEMO_STEPS[step - 1];
  const next = DEMO_STEPS[step];
  const text = describe(step, pathname);

  const go = (target: (typeof DEMO_STEPS)[number]) => {
    setDemoStep(target.number);
    router.push(target.start);
  };

  return (
    <>
      {/* Room at the end of the page, so the bar never hides the last of its content. */}
      <div className="h-32" aria-hidden />
      <div role="region" aria-label="Guided tour" className="fixed inset-x-0 bottom-0 z-50 px-4 pb-4 pointer-events-none">
        <div className="pointer-events-auto mx-auto max-w-2xl rounded-2xl border border-border bg-card/95 px-4 py-3 shadow-lg backdrop-blur">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-medium uppercase tracking-wider text-primary">
              Tour · Step {step} of {DEMO_STEPS.length} · {current.title}
            </p>
            <button
              onClick={() => setDemoStep(null)}
              className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="h-3 w-3" />
              End tour
            </button>
          </div>

          <p className="mt-1 text-sm leading-relaxed text-foreground">{text ?? current.summary}</p>

          <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2">
            <div className="flex gap-1.5" aria-hidden>
              {DEMO_STEPS.map((s) => (
                <span
                  key={s.number}
                  className={cn('h-1.5 w-6 rounded-full', s.number <= step ? 'bg-primary' : 'bg-border')}
                />
              ))}
            </div>
            <div className="flex gap-2">
              {!text && (
                // Somewhere the step doesn't cover (History, say): offer its start again.
                <Button size="sm" variant="outline" onClick={() => go(current)}>
                  {current.action}
                </Button>
              )}
              {next ? (
                <Button size="sm" className="gap-1.5" onClick={() => go(next)}>
                  Next: {next.title}
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              ) : (
                <Button
                  size="sm"
                  onClick={() => {
                    setDemoStep(null);
                    router.push('/');
                  }}
                >
                  Finish the tour
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
