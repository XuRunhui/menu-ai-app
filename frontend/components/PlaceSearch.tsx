'use client';

import { useState } from 'react';
import { searchPlaces, GooglePlace } from '@/lib/api';

interface PlaceSearchProps {
  onPlaceSelected: (placeId: string, placeName: string) => void;
}

export default function PlaceSearch({ onPlaceSelected }: PlaceSearchProps) {
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<GooglePlace[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPlaceId, setSelectedPlaceId] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!query.trim()) {
      setError('Please enter a restaurant name or search term');
      return;
    }

    setIsSearching(true);
    setError(null);
    setSearchResults([]);
    setSelectedPlaceId(null);

    try {
      const result = await searchPlaces(query);

      if (result.status !== 'OK' && result.status !== 'ZERO_RESULTS') {
        throw new Error(`Search failed: ${result.status}`);
      }

      if (result.results.length === 0) {
        setError('No restaurants found. Try a different search term.');
      } else if (result.results.length === 1) {
        // Auto-select if only one result
        const place = result.results[0];
        setSelectedPlaceId(place.place_id);
        onPlaceSelected(place.place_id, place.name);
        setSearchResults(result.results);
      } else {
        setSearchResults(result.results);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred while searching');
    } finally {
      setIsSearching(false);
    }
  };

  const handleSelectPlace = (place: GooglePlace) => {
    setSelectedPlaceId(place.place_id);
    onPlaceSelected(place.place_id, place.name);
  };

  const renderStars = (rating?: number) => {
    if (!rating) return null;

    const fullStars = Math.floor(rating);
    const hasHalfStar = rating % 1 >= 0.5;
    const stars = [];

    for (let i = 0; i < fullStars; i++) {
      stars.push(
        <span key={`full-${i}`} className="text-yellow-400">
          ★
        </span>
      );
    }

    if (hasHalfStar) {
      stars.push(
        <span key="half" className="text-yellow-400">
          ⯨
        </span>
      );
    }

    const emptyStars = 5 - stars.length;
    for (let i = 0; i < emptyStars; i++) {
      stars.push(
        <span key={`empty-${i}`} className="text-gray-300">
          ★
        </span>
      );
    }

    return <div className="flex items-center gap-1">{stars}</div>;
  };

  const formatPriceLevel = (priceLevel?: number) => {
    if (priceLevel === undefined || priceLevel === null) return null;
    return '$'.repeat(priceLevel + 1);
  };

  return (
    <div className="w-full max-w-4xl mx-auto p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Find Your Restaurant</h2>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="space-y-4 mb-6">
        <div>
          <label htmlFor="restaurant-query" className="block text-sm font-medium text-gray-700 mb-2">
            Restaurant Name or Search Term
          </label>
          <input
            id="restaurant-query"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g., 'tofu house koreatown' or 'best sushi downtown'"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isSearching}
          />
          <p className="mt-1 text-xs text-gray-500">
            Tip: You can search by name, cuisine type, or neighborhood
          </p>
        </div>

        <button
          type="submit"
          disabled={isSearching || !query.trim()}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {isSearching ? 'Searching...' : 'Search Restaurants'}
        </button>
      </form>

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800 text-sm">{error}</p>
        </div>
      )}

      {/* Search Results */}
      {searchResults.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-800">
            {searchResults.length === 1 ? 'Result' : `${searchResults.length} Results`} - Select Your Restaurant
          </h3>

          <div className="grid gap-4">
            {searchResults.map((place) => (
              <div
                key={place.place_id}
                onClick={() => handleSelectPlace(place)}
                className={`p-4 border rounded-lg cursor-pointer transition-all ${
                  selectedPlaceId === place.place_id
                    ? 'border-blue-500 bg-blue-50 shadow-md'
                    : 'border-gray-200 hover:border-blue-300 hover:shadow-sm'
                }`}
              >
                <div className="flex justify-between items-start">
                  {/* Restaurant Info */}
                  <div className="flex-1 min-w-0">
                    <h4 className="text-lg font-semibold text-gray-800 truncate">{place.name}</h4>

                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      {place.rating && (
                        <>
                          {renderStars(place.rating)}
                          <span className="text-sm text-gray-600">
                            {place.rating} {place.user_ratings_total && `(${place.user_ratings_total.toLocaleString()} reviews)`}
                          </span>
                        </>
                      )}
                      {formatPriceLevel(place.price_level) && (
                        <span className="text-sm font-medium text-green-600 ml-2">
                          {formatPriceLevel(place.price_level)}
                        </span>
                      )}
                    </div>

                    <div className="mt-2">
                      <p className="text-sm text-gray-600">{place.formatted_address}</p>
                    </div>

                    {place.types && place.types.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {place.types.filter(t => !t.includes('_')).slice(0, 3).map((type) => (
                          <span
                            key={type}
                            className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded-full capitalize"
                          >
                            {type.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    )}

                    {place.business_status && place.business_status !== 'OPERATIONAL' && (
                      <div className="mt-2">
                        <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded-full">
                          {place.business_status === 'CLOSED_TEMPORARILY' ? 'Temporarily Closed' : place.business_status}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Selection Indicator */}
                  {selectedPlaceId === place.place_id && (
                    <div className="flex-shrink-0 ml-4">
                      <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                        <svg
                          className="w-5 h-5 text-white"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Success Message */}
      {selectedPlaceId && (
        <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-green-800 text-sm font-medium">
            Restaurant selected! Loading details...
          </p>
        </div>
      )}
    </div>
  );
}
