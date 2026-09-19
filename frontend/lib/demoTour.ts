'use client';

import { useSyncExternalStore } from 'react';

/**
 * The guided tour: three steps, each running one of the app's features for real on sample input.
 *
 * The step the visitor is on is kept in sessionStorage, so it follows them from page to page (and
 * through a refresh) but ends with the tab. Each step starts from a URL with ?demo=<step>, which
 * the page it lands on reads once to fill in the sample and run it.
 */

export interface DemoStep {
  number: 1 | 2 | 3;
  title: string;
  summary: string;
  /** What the visitor will see, for the tour page. */
  shows: string[];
  action: string;
  start: string;
}

/** A restaurant whose website has a menu the reader handles well (61 dishes from its PDF). */
export const DEMO_RESTAURANT_QUERY = 'Noodle St. UCLA';
/** Answered with restaurants in one turn, rather than a follow-up question. */
export const DEMO_ASSISTANT_PROMPT =
  'Something spicy and not too expensive near Koreatown, Los Angeles, within walking distance';

export const DEMO_STEPS: DemoStep[] = [
  {
    number: 1,
    title: 'Read a menu photo',
    summary: 'A photo of a real menu becomes a menu you can browse.',
    shows: [
      'Every dish listed by category, with its price',
      'A photo found for each dish',
      'Combos of dishes that go well together, and why',
    ],
    action: 'Read the sample menu',
    start: '/search?mode=upload&demo=1',
  },
  {
    number: 2,
    title: 'Look up a restaurant',
    summary: 'Pick a restaurant from Google, and its menu is put together for you.',
    shows: [
      'The menu read from the restaurant’s own website',
      'Dishes that reviewers mention, starred',
      'Where every dish came from, and a way to add your own menu photo',
    ],
    action: `Look up ${DEMO_RESTAURANT_QUERY}`,
    start: '/search?mode=places&demo=2',
  },
  {
    number: 3,
    title: 'Ask the assistant',
    summary: 'Say what you feel like, where you are, and how far you’ll walk.',
    shows: [
      'Real restaurants nearby, with rating and distance',
      'What to order there',
      'One tap to open a restaurant’s menu',
    ],
    action: 'Ask for something spicy near Koreatown',
    start: '/assistant?demo=3',
  },
];

const KEY = 'menuist.demo.step';
const listeners = new Set<() => void>();

function readStep(): number | null {
  try {
    const value = Number(window.sessionStorage.getItem(KEY));
    return value >= 1 && value <= DEMO_STEPS.length ? value : null;
  } catch {
    return null; // storage blocked: the steps still run, just without the guide
  }
}

/** Start a step (1-3), or end the tour with null. */
export function setDemoStep(step: number | null): void {
  try {
    if (step) window.sessionStorage.setItem(KEY, String(step));
    else window.sessionStorage.removeItem(KEY);
  } catch {
    // ignore
  }
  listeners.forEach((listener) => listener());
}

/** The tour step in progress, or null; re-renders when it changes. */
export function useDemoStep(): number | null {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    readStep,
    () => null
  );
}
