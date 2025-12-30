/**
 * API client for the Menu AI backend.
 */

import { ParsedMenu } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Parse a menu image using the backend API.
 *
 * @param imageFile - The image file to parse
 * @returns Parsed menu structure with categories and items
 * @throws Error if the API request fails
 */
export async function parseMenu(imageFile: File): Promise<ParsedMenu> {
  const formData = new FormData();
  formData.append('image', imageFile);

  const response = await fetch(`${API_BASE_URL}/api/v1/menu/parse`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error ${response.status}`);
  }

  return response.json();
}
