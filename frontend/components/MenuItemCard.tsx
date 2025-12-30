/**
 * Card component for displaying a single menu item.
 */

import { MenuItem } from '@/lib/types';

interface MenuItemCardProps {
  item: MenuItem;
}

export default function MenuItemCard({ item }: MenuItemCardProps) {
  return (
    <div className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-2">
        <h3 className="text-lg font-semibold text-gray-900">{item.name}</h3>
        <span className="text-lg font-bold text-green-600">
          ${item.price.toFixed(2)}
        </span>
      </div>
      {item.description && (
        <p className="text-sm text-gray-600">{item.description}</p>
      )}
    </div>
  );
}
