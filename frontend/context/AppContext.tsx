'use client';

import React, { createContext, useContext, useReducer, useCallback } from 'react';
import type { ParsedMenu } from '@/lib/types';
import type { CombinedMenu, PlaceDetailsResponse, PopularDish, SourceResult, SourcedMenu } from '@/lib/api';
import { buildRecommendedSet, isRecommended } from '@/lib/utils/dishMatcher';

// ─── Types ──────────────────────────────────────────────────────────────────

export interface RestaurantInfo {
  place_id: string;
  name: string;
  location: string;
  rating?: number;
  user_ratings_total?: number;
  price_level?: number;
  website?: string;
  formatted_phone_number?: string;
}

/**
 * A restaurant's menu as it's being assembled from its website, its reviews and any photos the
 * diner adds. Each source is kept separately so it can be labelled, and so a
 * later upload can be merged with everything found before it.
 */
export interface MenuSourcesState {
  placeId: string;
  /** Results per readable source; undefined while that source is still being checked. */
  website?: SourceResult;
  /** Menu photos the diner added, one entry per photo. */
  uploads: SourcedMenu[];
  combined: CombinedMenu | null;
}

interface AppState {
  entryMode: 'upload' | 'places' | null;
  restaurant: RestaurantInfo | null;
  parsedMenu: ParsedMenu | null;
  targetLanguage: string | null;
  placeDetails: PlaceDetailsResponse | null;
  popularDishes: PopularDish[];
  recommendedDishNames: Set<string>;
  menuSources: MenuSourcesState | null;
  /** Set when the assistant opened this restaurant, so Back returns to the conversation. */
  openedFrom: 'assistant' | null;
}

/** How a restaurant was opened: sources already read, and whether the assistant opened it. */
export interface OpenPlaceOptions {
  menuSources?: MenuSourcesState | null;
  from?: 'assistant';
}

type AppAction =
  | { type: 'SET_ENTRY_MODE'; payload: 'upload' | 'places' }
  | { type: 'UPDATE_MENU_SOURCES'; payload: (current: MenuSourcesState | null) => MenuSourcesState | null }
  | { type: 'OPEN_PLACE'; payload: { details: PlaceDetailsResponse; options: OpenPlaceOptions } }
  | { type: 'OPEN_MENU'; payload: { menu: ParsedMenu; language: string | null; restaurantName: string | null } }
  | { type: 'RESET' };

interface AppContextValue extends AppState {
  /**
   * Query string identifying the current results ("?menu=12" or "?place=ChIJ...").
   * Added to results/dish URLs so a signed-in user's page can be restored after a refresh.
   */
  resultsQuery: string;
  setEntryMode: (mode: 'upload' | 'places') => void;
  /** Functional update, so sources finishing at the same moment can't overwrite each other. */
  updateMenuSources: (update: (current: MenuSourcesState | null) => MenuSourcesState | null) => void;
  /**
   * Show a restaurant from Google, replacing whatever was open before. `menuSources` hands over
   * sources already read (the assistant reads the website before offering the menu).
   */
  openPlace: (details: PlaceDetailsResponse, options?: OpenPlaceOptions) => void;
  /** Show an uploaded menu, replacing whatever was open before. */
  openMenu: (menu: ParsedMenu, language: string | null, restaurantName?: string | null) => void;
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
  menuSources: null,
  openedFrom: null,
};

// ─── Reducer ─────────────────────────────────────────────────────────────────

function restaurantFrom(details: PlaceDetailsResponse): RestaurantInfo {
  const place = details.place;
  return {
    place_id: place.place_id,
    name: place.name,
    location: place.formatted_address ?? '',
    rating: place.rating,
    user_ratings_total: place.user_ratings_total,
    price_level: place.price_level,
    website: place.website,
    formatted_phone_number: place.formatted_phone_number,
  };
}

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
          menuSources: null,
        };
      }
    }

    case 'UPDATE_MENU_SOURCES':
      return { ...state, menuSources: action.payload(state.menuSources) };

    // Opening a restaurant or a menu starts from nothing. Keeping anything from the previous one
    // showed an old uploaded menu under a restaurant the assistant had just opened.
    case 'OPEN_PLACE': {
      const { details, options } = action.payload;
      const popularDishes = details.popular_dishes ?? [];
      return {
        ...initialState,
        entryMode: 'places',
        placeDetails: details,
        restaurant: restaurantFrom(details),
        popularDishes,
        recommendedDishNames: buildRecommendedSet(popularDishes),
        menuSources: options.menuSources ?? null,
        openedFrom: options.from ?? null,
      };
    }

    case 'OPEN_MENU': {
      const { menu, language, restaurantName } = action.payload;
      const name = restaurantName?.trim();
      return {
        ...initialState,
        recommendedDishNames: new Set<string>(),
        entryMode: 'upload',
        parsedMenu: menu,
        targetLanguage: language,
        restaurant: name ? { place_id: '', name, location: '' } : null,
      };
    }

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

  const updateMenuSources = useCallback(
    (update: (current: MenuSourcesState | null) => MenuSourcesState | null) => {
      dispatch({ type: 'UPDATE_MENU_SOURCES', payload: update });
    },
    []
  );

  const openPlace = useCallback((details: PlaceDetailsResponse, options: OpenPlaceOptions = {}) => {
    dispatch({ type: 'OPEN_PLACE', payload: { details, options } });
  }, []);

  const openMenu = useCallback((menu: ParsedMenu, language: string | null, restaurantName: string | null = null) => {
    dispatch({ type: 'OPEN_MENU', payload: { menu, language, restaurantName } });
  }, []);

  const resetSession = useCallback(() => {
    dispatch({ type: 'RESET' });
  }, []);

  const checkIsRecommended = useCallback((dishName: string) => {
    return isRecommended(dishName, state.recommendedDishNames);
  }, [state.recommendedDishNames]);

  let resultsQuery = '';
  if (state.parsedMenu?.menu_id) {
    resultsQuery = `?menu=${state.parsedMenu.menu_id}`;
  } else if (!state.parsedMenu && state.restaurant?.place_id) {
    resultsQuery = `?place=${encodeURIComponent(state.restaurant.place_id)}`;
  }

  const value: AppContextValue = {
    ...state,
    resultsQuery,
    setEntryMode,
    updateMenuSources,
    openPlace,
    openMenu,
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
