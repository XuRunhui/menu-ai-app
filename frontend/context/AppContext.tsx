'use client';

import React, { createContext, useContext, useReducer, useCallback } from 'react';
import type { ParsedMenu } from '@/lib/types';
import type { PlaceDetailsResponse, PopularDish } from '@/lib/api';
import { buildRecommendedSet, isRecommended } from '@/lib/utils/dishMatcher';

// ─── Types ──────────────────────────────────────────────────────────────────

export interface RestaurantInfo {
  place_id: string;
  name: string;
  location: string;
  rating?: number;
  user_ratings_total?: number;
  price_level?: number;
  photo_urls?: string[];
  website?: string;
  formatted_phone_number?: string;
}

interface AppState {
  entryMode: 'upload' | 'places' | null;
  restaurant: RestaurantInfo | null;
  parsedMenu: ParsedMenu | null;
  targetLanguage: string | null;
  placeDetails: PlaceDetailsResponse | null;
  popularDishes: PopularDish[];
  recommendedDishNames: Set<string>;
  knowledgeBaseStatus: 'idle' | 'building' | 'ready' | 'error';
}

type AppAction =
  | { type: 'SET_ENTRY_MODE'; payload: 'upload' | 'places' }
  | { type: 'SET_RESTAURANT'; payload: RestaurantInfo }
  | { type: 'SET_PARSED_MENU'; payload: { menu: ParsedMenu; language: string | null } }
  | { type: 'SET_PLACE_DETAILS'; payload: PlaceDetailsResponse }
  | { type: 'SET_KB_STATUS'; payload: AppState['knowledgeBaseStatus'] }
  | { type: 'RESET' };

interface AppContextValue extends AppState {
  setEntryMode: (mode: 'upload' | 'places') => void;
  setRestaurant: (info: RestaurantInfo) => void;
  setParsedMenu: (menu: ParsedMenu, language: string | null) => void;
  setPlaceDetails: (details: PlaceDetailsResponse) => void;
  setKnowledgeBaseStatus: (status: AppState['knowledgeBaseStatus']) => void;
  resetSession: () => void;
  checkIsRecommended: (dishName: string) => boolean;
}

// ─── Initial State ───────────────────────────────────────────────────────────

const initialState: AppState = {
  entryMode: null,
  restaurant: null,
  parsedMenu: null,
  targetLanguage: null,
  placeDetails: null,
  popularDishes: [],
  recommendedDishNames: new Set<string>(),
  knowledgeBaseStatus: 'idle',
};

// ─── Reducer ─────────────────────────────────────────────────────────────────

function reducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_ENTRY_MODE': {
      const newMode = action.payload;
      if (newMode === state.entryMode) return { ...state, entryMode: newMode };
      // Switching modes: clear data from the previous flow to prevent stale results
      if (newMode === 'places') {
        // Entering Places flow — clear any previously uploaded menu
        return {
          ...state,
          entryMode: newMode,
          parsedMenu: null,
          targetLanguage: null,
        };
      } else {
        // Entering Upload flow — clear any previously fetched place data
        return {
          ...state,
          entryMode: newMode,
          placeDetails: null,
          restaurant: null,
          popularDishes: [],
          recommendedDishNames: new Set<string>(),
          knowledgeBaseStatus: 'idle',
        };
      }
    }

    case 'SET_RESTAURANT':
      return { ...state, restaurant: action.payload };

    case 'SET_PARSED_MENU':
      return {
        ...state,
        parsedMenu: action.payload.menu,
        targetLanguage: action.payload.language,
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
        user_ratings_total: details.place.user_ratings_total,
        price_level: details.place.price_level,
        photo_urls: details.place.photo_urls ?? [],
        website: details.place.website,
        formatted_phone_number: details.place.formatted_phone_number,
      };

      return {
        ...state,
        placeDetails: details,
        popularDishes,
        recommendedDishNames,
        restaurant: state.restaurant ?? restaurant,
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

// ─── Context ─────────────────────────────────────────────────────────────────

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, {
    ...initialState,
    recommendedDishNames: new Set<string>(),
  });

  const setEntryMode = useCallback((mode: 'upload' | 'places') => {
    dispatch({ type: 'SET_ENTRY_MODE', payload: mode });
  }, []);

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
    setEntryMode,
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
  if (!ctx) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return ctx;
}
