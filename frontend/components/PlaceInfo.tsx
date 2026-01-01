'use client';

import { useState, useEffect } from 'react';
import { getPlaceDetails, PlaceDetailsResponse } from '@/lib/api';

interface PlaceInfoProps {
  placeId: string;
}

export default function PlaceInfo({ placeId }: PlaceInfoProps) {
  const [placeData, setPlaceData] = useState<PlaceDetailsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPhotoIndex, setSelectedPhotoIndex] = useState(0);

  useEffect(() => {
    const fetchPlaceData = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const data = await getPlaceDetails(placeId);
        setPlaceData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred while fetching data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchPlaceData();
  }, [placeId]);

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

  const formatPriceLevel = (priceLevel?: number) => {
    if (priceLevel === undefined || priceLevel === null) return null;
    return '$'.repeat(priceLevel + 1);
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

  if (!placeData) {
    return null;
  }

  const { place, reviews, popular_dishes } = placeData;
  const photoUrls = place.photo_urls || [];

  return (
    <div className="w-full max-w-4xl mx-auto p-6 bg-white rounded-lg shadow-md space-y-6">
      {/* Restaurant Header */}
      <div className="border-b pb-6">
        <h2 className="text-3xl font-bold text-gray-800 mb-2">{place.name}</h2>

        <div className="flex items-center gap-4 mb-4 flex-wrap">
          {place.rating && renderStars(place.rating)}
          {place.rating && (
            <span className="text-lg text-gray-700 font-medium">{place.rating}</span>
          )}
          {place.user_ratings_total && (
            <span className="text-gray-500">({place.user_ratings_total.toLocaleString()} reviews)</span>
          )}
          {formatPriceLevel(place.price_level) && (
            <span className="text-lg font-semibold text-green-600">{formatPriceLevel(place.price_level)}</span>
          )}
        </div>

        <div className="space-y-2 text-gray-600">
          <p>{place.formatted_address}</p>
          {place.formatted_phone_number && <p>Phone: {place.formatted_phone_number}</p>}
          {place.website && (
            <p>
              <a
                href={place.website}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800"
              >
                Visit Website →
              </a>
            </p>
          )}
        </div>
      </div>

      {/* Photo Gallery */}
      {photoUrls.length > 0 && (
        <div className="border-b pb-6">
          <h3 className="text-xl font-semibold text-gray-800 mb-4">Photos</h3>

          <div className="space-y-4">
            {/* Main Photo */}
            <div className="w-full h-96 bg-gray-100 rounded-lg overflow-hidden">
              <img
                src={photoUrls[selectedPhotoIndex]}
                alt={`${place.name} photo ${selectedPhotoIndex + 1}`}
                className="w-full h-full object-cover"
              />
            </div>

            {/* Photo Thumbnails */}
            {photoUrls.length > 1 && (
              <div className="flex gap-2 overflow-x-auto pb-2">
                {photoUrls.map((photoUrl, index) => (
                  <button
                    key={index}
                    onClick={() => setSelectedPhotoIndex(index)}
                    className={`flex-shrink-0 w-20 h-20 rounded-lg overflow-hidden border-2 transition-all ${
                      selectedPhotoIndex === index
                        ? 'border-blue-500 shadow-md'
                        : 'border-gray-200 hover:border-blue-300'
                    }`}
                  >
                    <img src={photoUrl} alt={`Thumbnail ${index + 1}`} className="w-full h-full object-cover" />
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Popular Dishes */}
      {popular_dishes.length > 0 ? (
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
      ) : (
        <div className="border-b pb-6">
          <h3 className="text-xl font-semibold text-gray-800 mb-4">Popular Dishes</h3>
          <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg text-center">
            <p className="text-gray-600">
              No popular dishes extracted. This restaurant may not have enough reviews with dish mentions.
            </p>
          </div>
        </div>
      )}

      {/* Recent Reviews */}
      <div>
        <h3 className="text-xl font-semibold text-gray-800 mb-4">Recent Reviews</h3>

        {reviews.length > 0 ? (
          <div className="space-y-4">
            {reviews.map((review, index) => (
              <div key={index} className="p-4 bg-gray-50 border border-gray-200 rounded-lg">
                <div className="flex items-start gap-4">
                  {/* User Avatar */}
                  {review.profile_photo_url ? (
                    <img
                      src={review.profile_photo_url}
                      alt={review.author_name}
                      className="w-12 h-12 rounded-full object-cover"
                      onError={(e) => {
                        // Hide broken image and show fallback
                        e.currentTarget.style.display = 'none';
                        const fallback = e.currentTarget.nextElementSibling as HTMLElement;
                        if (fallback) fallback.style.display = 'flex';
                      }}
                    />
                  ) : null}
                  <div
                    className="w-12 h-12 rounded-full bg-gray-300 flex items-center justify-center text-gray-600 font-semibold"
                    style={{ display: review.profile_photo_url ? 'none' : 'flex' }}
                  >
                    {review.author_name.charAt(0).toUpperCase()}
                  </div>

                  {/* Review Content */}
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className="font-semibold text-gray-800">{review.author_name}</span>
                      {renderStars(review.rating)}
                      <span className="text-sm text-gray-500">{review.relative_time_description}</span>
                    </div>

                    <p className="text-gray-700 leading-relaxed">{review.text}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-6 bg-gray-50 border border-gray-200 rounded-lg text-center">
            <p className="text-gray-600">No reviews available for this restaurant.</p>
          </div>
        )}
      </div>
    </div>
  );
}
