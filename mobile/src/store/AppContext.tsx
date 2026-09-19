import React, { createContext, useContext, useReducer, useCallback } from 'react';
import {
  ParsedMenu,
  PlaceDetailsResponse,
  PopularDish,
  RestaurantInfo,
} from '@/types';

// ─── Recommended dish matching ────────────────────────────────────────────────

function normalize(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9\s]/g, '').trim();
}

function jaccardSimilarity(a: string, b: string): number {
  const setA = new Set(a.split(/\s+/));
  const setB = new Set(b.split(/\s+/));
  let intersection = 0;
  setA.forEach((w) => { if (setB.has(w)) intersection++; });
  const union = setA.size + setB.size - intersection;
  return union === 0 ? 0 : intersection / union;
}

function buildRecommendedSet(dishes: PopularDish[]): Set<string> {
  return new Set(dishes.map((d) => normalize(d.name)));
}

function isRecommended(name: string, set: Set<string>): boolean {
  const n = normalize(name);
  if (set.has(n)) return true;
  for (const candidate of set) {
    if (jaccardSimilarity(n, candidate) >= 0.5) return true;
  }
  return false;
}

// ─── State & Actions ──────────────────────────────────────────────────────────

interface AppState {
  restaurant: RestaurantInfo | null;
  parsedMenu: ParsedMenu | null;
  targetLanguage: string | null;
  placeDetails: PlaceDetailsResponse | null;
  popularDishes: PopularDish[];
  recommendedDishNames: Set<string>;
  knowledgeBaseStatus: 'idle' | 'building' | 'ready' | 'error';
}

type AppAction =
  | { type: 'SET_RESTAURANT'; payload: RestaurantInfo }
  | { type: 'SET_PARSED_MENU'; payload: { menu: ParsedMenu; language: string | null } }
  | { type: 'SET_PLACE_DETAILS'; payload: PlaceDetailsResponse }
  | { type: 'SET_KB_STATUS'; payload: AppState['knowledgeBaseStatus'] }
  | { type: 'RESET' };

const initialState: AppState = {
  restaurant: null,
  parsedMenu: null,
  targetLanguage: null,
  placeDetails: null,
  popularDishes: [],
  recommendedDishNames: new Set<string>(),
  knowledgeBaseStatus: 'idle',
};

function reducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_RESTAURANT':
      return { ...state, restaurant: action.payload };

    case 'SET_PARSED_MENU':
      return {
        ...state,
        parsedMenu: action.payload.menu,
        targetLanguage: action.payload.language,
        // Clear popular dishes so dish list uses the uploaded menu
        popularDishes: [],
        recommendedDishNames: new Set<string>(),
      };

    case 'SET_PLACE_DETAILS': {
      const details = action.payload;
      const popularDishes = details.popular_dishes ?? [];
      const recommendedDishNames = buildRecommendedSet(popularDishes);

      const restaurant: RestaurantInfo = {
        place_id: details.place.place_id,
        name: details.place.name,
        location: details.place.formatted_address ?? '',
        rating: details.place.rating,
        photo_urls: details.place.photo_urls ?? [],
      };

      return {
        ...state,
        placeDetails: details,
        popularDishes,
        recommendedDishNames,
        restaurant: state.restaurant ?? restaurant,
        parsedMenu: null,       // clear any previously uploaded menu
        targetLanguage: null,
      };
    }

    case 'SET_KB_STATUS':
      return { ...state, knowledgeBaseStatus: action.payload };

    case 'RESET':
      return { ...initialState, recommendedDishNames: new Set<string>() };

    default:
      return state;
  }
}

// ─── Context ──────────────────────────────────────────────────────────────────

interface AppContextValue extends AppState {
  setRestaurant: (info: RestaurantInfo) => void;
  setParsedMenu: (menu: ParsedMenu, language: string | null) => void;
  setPlaceDetails: (details: PlaceDetailsResponse) => void;
  setKnowledgeBaseStatus: (status: AppState['knowledgeBaseStatus']) => void;
  resetSession: () => void;
  checkIsRecommended: (dishName: string) => boolean;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, {
    ...initialState,
    recommendedDishNames: new Set<string>(),
  });

  const setRestaurant = useCallback((info: RestaurantInfo) => {
    dispatch({ type: 'SET_RESTAURANT', payload: info });
  }, []);

  const setParsedMenu = useCallback((menu: ParsedMenu, language: string | null) => {
    dispatch({ type: 'SET_PARSED_MENU', payload: { menu, language } });
  }, []);

  const setPlaceDetails = useCallback((details: PlaceDetailsResponse) => {
    dispatch({ type: 'SET_PLACE_DETAILS', payload: details });
  }, []);

  const setKnowledgeBaseStatus = useCallback((status: AppState['knowledgeBaseStatus']) => {
    dispatch({ type: 'SET_KB_STATUS', payload: status });
  }, []);

  const resetSession = useCallback(() => {
    dispatch({ type: 'RESET' });
  }, []);

  const checkIsRecommended = useCallback((dishName: string) => {
    return isRecommended(dishName, state.recommendedDishNames);
  }, [state.recommendedDishNames]);

  const value: AppContextValue = {
    ...state,
    setRestaurant,
    setParsedMenu,
    setPlaceDetails,
    setKnowledgeBaseStatus,
    resetSession,
    checkIsRecommended,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppContext must be used inside AppProvider');
  return ctx;
}
