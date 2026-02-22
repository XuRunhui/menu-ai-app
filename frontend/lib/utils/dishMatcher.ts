import type { PopularDish } from '@/lib/api';

const STOP_WORDS = new Set(['the', 'a', 'an', 'with', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for']);

function normalize(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^\w\s]/g, '')
    .replace(/\s+/g, ' ');
}

function tokenize(normalized: string): string[] {
  return normalized.split(' ').filter(t => t.length > 0 && !STOP_WORDS.has(t));
}

function jaccardSimilarity(a: string[], b: string[]): number {
  if (a.length === 0 && b.length === 0) return 1;
  const setA = new Set(a);
  const setB = new Set(b);
  const intersection = [...setA].filter(x => setB.has(x)).length;
  const union = new Set([...setA, ...setB]).size;
  return union === 0 ? 0 : intersection / union;
}

function namesMatch(menuName: string, popularName: string): boolean {
  const normA = normalize(menuName);
  const normB = normalize(popularName);

  if (normA === normB) return true;
  if (normA.includes(normB) || normB.includes(normA)) return true;

  const tokensA = tokenize(normA);
  const tokensB = tokenize(normB);

  return jaccardSimilarity(tokensA, tokensB) >= 0.5;
}

/**
 * Build a Set of normalized popular dish names for O(1) lookup.
 * Stores both the normalized full name and individual significant tokens
 * to enable flexible matching.
 */
export function buildRecommendedSet(popularDishes: PopularDish[]): Set<string> {
  const set = new Set<string>();
  for (const dish of popularDishes) {
    set.add(normalize(dish.name));
  }
  return set;
}

/**
 * Check if a menu item name matches any popular dish.
 * The set contains normalized popular dish names; we compare the
 * incoming name against each using fuzzy logic.
 */
export function isRecommended(menuItemName: string, recommendedSet: Set<string>): boolean {
  if (recommendedSet.size === 0) return false;
  const normalizedInput = normalize(menuItemName);
  for (const popularName of recommendedSet) {
    if (namesMatch(normalizedInput, popularName)) return true;
  }
  return false;
}
