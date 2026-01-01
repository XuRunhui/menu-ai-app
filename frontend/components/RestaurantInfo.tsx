'use client';

import { useState, useEffect } from 'react';

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

interface YelpCoordinates {
  latitude: number;
  longitude: number;
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
  coordinates: YelpCoordinates | null;
  phone: string | null;
  photos: string[];
}

interface YelpReview {
  id: string;
  text: string;
  rating: number;
  time_created: string;
  user: {
    name: string;
    image_url: string | null;
  };
}

interface PopularDish {
  name: string;
  mention_count: number;
  avg_sentiment: number;
  sample_reviews: string[];
}

interface RestaurantData {
  business: YelpBusiness;
  reviews: YelpReview[];
  popular_dishes: PopularDish[];
}

interface RestaurantInfoProps {
  businessId: string;
}

export default function RestaurantInfo({ businessId }: RestaurantInfoProps) {
  const [restaurantData, setRestaurantData] = useState<RestaurantData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPhotoIndex, setSelectedPhotoIndex] = useState(0);

  useEffect(() => {
    const fetchRestaurantData = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`http://localhost:8000/api/v1/restaurant/${businessId}`);

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed to fetch restaurant data');
        }

        const data = await response.json();
        setRestaurantData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred while fetching data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchRestaurantData();
  }, [businessId]);

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

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  if (isLoading) {
    return (
      <div className="w-full max-w-4xl mx-auto p-6 bg-white rounded-lg shadow-md">
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          <span className="ml-4 text-gray-600">Loading restaurant information...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full max-w-4xl mx-auto p-6 bg-white rounded-lg shadow-md">
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (!restaurantData) {
    return null;
  }

  const { business, reviews, popular_dishes } = restaurantData;

  return (
    <div className="w-full max-w-4xl mx-auto p-6 bg-white rounded-lg shadow-md space-y-6">
      {/* Restaurant Header */}
      <div className="border-b pb-6">
        <h2 className="text-3xl font-bold text-gray-800 mb-2">{business.name}</h2>

        <div className="flex items-center gap-4 mb-4">
          {renderStars(business.rating)}
          <span className="text-lg text-gray-700 font-medium">{business.rating}</span>
          <span className="text-gray-500">({business.review_count} reviews)</span>
          {business.price && (
            <span className="text-lg font-semibold text-green-600">{business.price}</span>
          )}
        </div>

        <div className="space-y-2 text-gray-600">
          <p>{business.location.display_address.join(', ')}</p>
          {business.phone && <p>Phone: {business.phone}</p>}

          {business.categories.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {business.categories.map((category) => (
                <span
                  key={category.alias}
                  className="bg-blue-100 text-blue-700 px-3 py-1 rounded-full text-sm"
                >
                  {category.title}
                </span>
              ))}
            </div>
          )}
        </div>

        <a
          href={business.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block mt-4 text-blue-600 hover:text-blue-800 font-medium"
        >
          View on Yelp →
        </a>
      </div>

      {/* Photo Gallery */}
      {business.photos.length > 0 && (
        <div className="border-b pb-6">
          <h3 className="text-xl font-semibold text-gray-800 mb-4">Photos</h3>

          <div className="space-y-4">
            {/* Main Photo */}
            <div className="w-full h-96 bg-gray-100 rounded-lg overflow-hidden">
              <img
                src={business.photos[selectedPhotoIndex]}
                alt={`${business.name} photo ${selectedPhotoIndex + 1}`}
                className="w-full h-full object-cover"
              />
            </div>

            {/* Photo Thumbnails */}
            {business.photos.length > 1 && (
              <div className="flex gap-2 overflow-x-auto pb-2">
                {business.photos.map((photo, index) => (
                  <button
                    key={index}
                    onClick={() => setSelectedPhotoIndex(index)}
                    className={`flex-shrink-0 w-20 h-20 rounded-lg overflow-hidden border-2 transition-all ${
                      selectedPhotoIndex === index
                        ? 'border-blue-500 shadow-md'
                        : 'border-gray-200 hover:border-blue-300'
                    }`}
                  >
                    <img src={photo} alt={`Thumbnail ${index + 1}`} className="w-full h-full object-cover" />
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Popular Dishes */}
      {popular_dishes.length > 0 && (
        <div className="border-b pb-6">
          <h3 className="text-xl font-semibold text-gray-800 mb-4">Popular Dishes from Reviews</h3>

          <div className="grid gap-3">
            {popular_dishes.map((dish, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-4 bg-gradient-to-r from-orange-50 to-yellow-50 border border-orange-200 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl font-bold text-orange-600">#{index + 1}</span>
                  <div>
                    <h4 className="text-lg font-semibold text-gray-800">{dish.name}</h4>
                    <p className="text-sm text-gray-600">
                      Mentioned {dish.mention_count} time{dish.mention_count > 1 ? 's' : ''} in reviews
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500">Sentiment:</span>
                  <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500"
                      style={{ width: `${dish.avg_sentiment * 100}%` }}
                    ></div>
                  </div>
                  <span className="text-sm font-medium text-gray-700">
                    {Math.round(dish.avg_sentiment * 100)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Reviews */}
      <div>
        <h3 className="text-xl font-semibold text-gray-800 mb-4">Recent Reviews</h3>

        {reviews.length > 0 ? (
          <div className="space-y-4">
            {reviews.map((review) => (
              <div key={review.id} className="p-4 bg-gray-50 border border-gray-200 rounded-lg">
                <div className="flex items-start gap-4">
                  {/* User Avatar */}
                  {review.user.image_url ? (
                    <img
                      src={review.user.image_url}
                      alt={review.user.name}
                      className="w-12 h-12 rounded-full object-cover"
                    />
                  ) : (
                    <div className="w-12 h-12 rounded-full bg-gray-300 flex items-center justify-center text-gray-600 font-semibold">
                      {review.user.name.charAt(0).toUpperCase()}
                    </div>
                  )}

                  {/* Review Content */}
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-semibold text-gray-800">{review.user.name}</span>
                      {renderStars(review.rating)}
                      <span className="text-sm text-gray-500">{formatDate(review.time_created)}</span>
                    </div>

                    <p className="text-gray-700 leading-relaxed">{review.text}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-6 bg-gray-50 border border-gray-200 rounded-lg text-center">
            <p className="text-gray-600">
              Reviews are not available for this restaurant. This may be because:
            </p>
            <ul className="mt-2 text-sm text-gray-500 list-disc list-inside">
              <li>The Yelp API Reviews endpoint requires additional permissions</li>
              <li>This restaurant doesn't have public reviews</li>
              <li>Your Yelp API key tier doesn't include reviews access</li>
            </ul>
            <p className="mt-3 text-sm text-gray-600">
              You can still view restaurant info and upload menus without reviews.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
