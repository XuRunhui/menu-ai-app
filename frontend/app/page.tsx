'use client';

/**
 * Main page with multilingual menu upload functionality.
 */

import { useState } from 'react';
import { parseMenu } from '@/lib/api';
import { ParsedMenu } from '@/lib/types';
import MenuItemCard from '@/components/MenuItemCard';
import PlaceSearch from '@/components/PlaceSearch';
import PlaceInfo from '@/components/PlaceInfo';

const SUPPORTED_LANGUAGES = [
  { code: null, name: 'No Translation' },
  { code: 'English', name: 'English' },
  { code: 'Chinese', name: '中文 (Chinese)' },
  { code: 'Japanese', name: '日本語 (Japanese)' },
  { code: 'Korean', name: '한국어 (Korean)' },
  { code: 'Spanish', name: 'Español (Spanish)' },
  { code: 'French', name: 'Français (French)' },
  { code: 'German', name: 'Deutsch (German)' },
  { code: 'Italian', name: 'Italiano (Italian)' },
  { code: 'Portuguese', name: 'Português (Portuguese)' },
  { code: 'Russian', name: 'Русский (Russian)' },
  { code: 'Arabic', name: 'العربية (Arabic)' },
  { code: 'Hindi', name: 'हिन्दी (Hindi)' },
];

export default function Home() {
  const [selectedRestaurantId, setSelectedRestaurantId] = useState<string | null>(null);
  const [selectedRestaurantName, setSelectedRestaurantName] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [targetLanguage, setTargetLanguage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parsedMenu, setParsedMenu] = useState<ParsedMenu | null>(null);
  const [showTranslation, setShowTranslation] = useState(true);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setError(null);
      setParsedMenu(null);
    }
  };

  const handleLanguageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    setTargetLanguage(value === '' ? null : value);
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select an image first');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await parseMenu(selectedFile, targetLanguage);
      setParsedMenu(result);
      setShowTranslation(!!targetLanguage);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to parse menu');
    } finally {
      setLoading(false);
    }
  };

  const handleRestaurantSelected = (businessId: string, businessName: string) => {
    setSelectedRestaurantId(businessId);
    setSelectedRestaurantName(businessName);
  };

  const hasTranslation = parsedMenu?.target_language;

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Multilingual Menu AI Parser
          </h1>
          <p className="text-gray-600">
            Upload a menu in any language and get AI-powered translations & recommendations
          </p>
        </header>

        {/* Step 1: Restaurant Search */}
        <div className="mb-8">
          <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <span className="inline-flex items-center justify-center w-8 h-8 bg-blue-500 text-white rounded-full font-bold">
                  1
                </span>
              </div>
              <div className="ml-3">
                <h3 className="text-lg font-medium text-blue-900">Find Your Restaurant (Optional)</h3>
                <p className="text-sm text-blue-700 mt-1">
                  Search for your restaurant to get popular dish recommendations from reviews
                </p>
              </div>
            </div>
          </div>
          <PlaceSearch onPlaceSelected={handleRestaurantSelected} />
        </div>

        {/* Restaurant Info Section */}
        {selectedRestaurantId && (
          <div className="mb-8">
            <PlaceInfo placeId={selectedRestaurantId} />
          </div>
        )}

        {/* Step 2: Menu Upload */}
        <div className="bg-green-50 border-l-4 border-green-500 p-4 mb-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <span className="inline-flex items-center justify-center w-8 h-8 bg-green-500 text-white rounded-full font-bold">
                2
              </span>
            </div>
            <div className="ml-3">
              <h3 className="text-lg font-medium text-green-900">Upload Menu Image</h3>
              <p className="text-sm text-green-700 mt-1">
                {selectedRestaurantName
                  ? `Upload the menu for ${selectedRestaurantName} to see AI-powered parsing`
                  : 'Upload any restaurant menu to get instant translations'}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Menu Image
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
            </div>

            {selectedFile && (
              <div className="text-sm text-gray-600">
                Selected: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Translate to (Optional)
              </label>
              <select
                value={targetLanguage || ''}
                onChange={handleLanguageChange}
                className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              >
                {SUPPORTED_LANGUAGES.map((lang) => (
                  <option key={lang.code || 'none'} value={lang.code || ''}>
                    {lang.name}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-gray-500">
                The menu language will be detected automatically
              </p>
            </div>

            <button
              onClick={handleUpload}
              disabled={!selectedFile || loading}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Parsing...' : 'Parse Menu'}
            </button>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
                {error}
              </div>
            )}
          </div>
        </div>

        {loading && (
          <div className="text-center py-8">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <p className="mt-2 text-gray-600">Analyzing menu image...</p>
          </div>
        )}

        {parsedMenu && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Parsed Menu</h2>
                {parsedMenu.detected_language && (
                  <p className="text-sm text-gray-600 mt-1">
                    Detected language: <span className="font-medium">{parsedMenu.detected_language}</span>
                    {parsedMenu.target_language && (
                      <> → Translated to: <span className="font-medium">{parsedMenu.target_language}</span></>
                    )}
                  </p>
                )}
              </div>

              {hasTranslation && (
                <button
                  onClick={() => setShowTranslation(!showTranslation)}
                  className="flex items-center gap-2 px-4 py-2 bg-white border-2 border-blue-600 text-blue-600 rounded-md font-medium hover:bg-blue-50 transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
                  </svg>
                  {showTranslation ? 'Show Original' : `Show ${parsedMenu.target_language}`}
                </button>
              )}
            </div>

            {parsedMenu.menu.map((category, idx) => (
              <div key={idx} className="bg-white rounded-lg shadow-md p-6">
                <div className="mb-4 border-b pb-2">
                  <h3 className="text-xl font-bold text-gray-800">
                    {showTranslation && category.category_translated
                      ? category.category_translated
                      : category.category}
                  </h3>
                  {category.category_translated && (
                    <p className="text-sm text-gray-500 mt-1">
                      {showTranslation ? category.category : category.category_translated}
                    </p>
                  )}
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  {category.items.map((item, itemIdx) => (
                    <MenuItemCard
                      key={itemIdx}
                      item={item}
                      showTranslation={showTranslation}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
