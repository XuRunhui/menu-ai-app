/**
 * Card component for displaying a single menu item with language toggle.
 */

import { MenuItem } from '@/lib/types';

interface MenuItemCardProps {
  item: MenuItem;
  showTranslation: boolean;
}

export default function MenuItemCard({ item, showTranslation }: MenuItemCardProps) {
  const hasTranslation = !!(item.name_translated || item.description_translated);

  const displayName = showTranslation && item.name_translated ? item.name_translated : item.name;
  const displayDescription = showTranslation && item.description_translated
    ? item.description_translated
    : item.description;

  // Format price display
  const formatPrice = () => {
    if (item.price_original) {
      // Show original price text (e.g., "八百円", "$12.50")
      return item.price_original;
    } else if (item.price !== null && item.price !== undefined) {
      // Show numeric price with currency
      const currency = item.currency || '$';
      return `${currency}${item.price.toFixed(2)}`;
    } else {
      // No price available
      return 'Market Price';
    }
  };

  return (
    <div className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-2">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900">{displayName}</h3>
          {hasTranslation && (
            <p className="text-xs text-gray-500 mt-1">
              {showTranslation ? item.name : item.name_translated}
            </p>
          )}
        </div>
        <div className="text-right ml-3">
          <span className="text-lg font-bold text-green-600">
            {formatPrice()}
          </span>
          {item.price !== null && item.price_original && (
            <p className="text-xs text-gray-500 mt-1">
              {item.currency || '$'}{item.price.toFixed(2)}
            </p>
          )}
        </div>
      </div>
      {displayDescription && (
        <p className="text-sm text-gray-600">{displayDescription}</p>
      )}
    </div>
  );
}
