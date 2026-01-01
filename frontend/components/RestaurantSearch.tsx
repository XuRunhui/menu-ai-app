'use client';

import { useState } from 'react';

interface YelpCategory {
  alias: string;
  title: string;
}

interface YelpLocation {
  address1: string | null;
  city: string;
  state: string;
  zip_code: string;
  country: string;
  display_address: string[];
}

interface YelpBusiness {
  id: string;
  name: string;
  image_url: string | null;
  url: string;
  rating: number;
  review_count: number;
  price: string | null;
  categories: YelpCategory[];
  location: YelpLocation;
  phone: string | null;
}

interface RestaurantSearchProps {
  onRestaurantSelected: (businessId: string, businessName: string) => void;
}

export default function RestaurantSearch({ onRestaurantSelected }: RestaurantSearchProps) {
  const [restaurantName, setRestaurantName] = useState('');
  const [location, setLocation] = useState('');
  const [searchResults, setSearchResults] = useState<YelpBusiness[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedBusinessId, setSelectedBusinessId] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!restaurantName.trim() || !location.trim()) {
      setError('Please enter both restaurant name and location');
      return;
    }

    setIsSearching(true);
    setError(null);
    setSearchResults([]);
    setSelectedBusinessId(null);

    try {
      const response = await fetch('http://localhost:8000/api/v1/restaurant/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: restaurantName,
          location: location,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to search restaurants');
      }

      const data = await response.json();

      if (data.businesses.length === 0) {
        setError('No restaurants found. Please try different search terms.');
      } else if (data.businesses.length === 1) {
        // Auto-select if only one result
        const business = data.businesses[0];
        setSelectedBusinessId(business.id);
        onRestaurantSelected(business.id, business.name);
      } else {
        setSearchResults(data.businesses);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred while searching');
    } finally {
      setIsSearching(false);
    }
  };

  const handleSelectRestaurant = (business: YelpBusiness) => {
    setSelectedBusinessId(business.id);
    onRestaurantSelected(business.id, business.name);
  };

  const renderStars = (rating: number) => {
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

  return (
    <div className="w-full max-w-4xl mx-auto p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Find Your Restaurant</h2>

      {/* Search Form */}
      <div className="space-y-4 mb-6">
        <div>
          <label htmlFor="restaurant-name" className="block text-sm font-medium text-gray-700 mb-2">
            Restaurant Name
          </label>
          <input
            id="restaurant-name"
            type="text"
            value={restaurantName}
            onChange={(e) => setRestaurantName(e.target.value)}
            placeholder="e.g., Joe's Pizza"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isSearching}
          />
        </div>

        <div>
          <label htmlFor="location" className="block text-sm font-medium text-gray-700 mb-2">
            Location
          </label>
          <input
            id="location"
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g., New York, NY or 10001"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isSearching}
          />
        </div>

        <button
          onClick={handleSearch}
          disabled={isSearching}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {isSearching ? 'Searching...' : 'Search Restaurants'}
        </button>
      </div>

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
            Select Your Restaurant ({searchResults.length} found)
          </h3>

          <div className="grid gap-4">
            {searchResults.map((business) => (
              <div
                key={business.id}
                onClick={() => handleSelectRestaurant(business)}
                className={`p-4 border rounded-lg cursor-pointer transition-all ${
                  selectedBusinessId === business.id
                    ? 'border-blue-500 bg-blue-50 shadow-md'
                    : 'border-gray-200 hover:border-blue-300 hover:shadow-sm'
                }`}
              >
                <div className="flex gap-4">
                  {/* Restaurant Image */}
                  {business.image_url && (
                    <div className="flex-shrink-0">
                      <img
                        src={business.image_url}
                        alt={business.name}
                        className="w-24 h-24 object-cover rounded-lg"
                      />
                    </div>
                  )}

                  {/* Restaurant Info */}
                  <div className="flex-1 min-w-0">
                    <h4 className="text-lg font-semibold text-gray-800 truncate">{business.name}</h4>

                    <div className="flex items-center gap-2 mt-1">
                      {renderStars(business.rating)}
                      <span className="text-sm text-gray-600">
                        {business.rating} ({business.review_count} reviews)
                      </span>
                      {business.price && (
                        <span className="text-sm font-medium text-green-600">{business.price}</span>
                      )}
                    </div>

                    <div className="mt-2">
                      <p className="text-sm text-gray-600">
                        {business.location.display_address.join(', ')}
                      </p>
                    </div>

                    {business.categories.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {business.categories.slice(0, 3).map((category) => (
                          <span
                            key={category.alias}
                            className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded-full"
                          >
                            {category.title}
                          </span>
                        ))}
                      </div>
                    )}

                    {business.phone && (
                      <p className="text-sm text-gray-500 mt-2">{business.phone}</p>
                    )}
                  </div>

                  {/* Selection Indicator */}
                  {selectedBusinessId === business.id && (
                    <div className="flex-shrink-0 flex items-center">
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
      {selectedBusinessId && (
        <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-green-800 text-sm font-medium">
            Restaurant selected! You can now upload the menu image.
          </p>
        </div>
      )}
    </div>
  );
}
