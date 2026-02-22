'use client';

import { useState, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Upload, FileImage, Loader2, ChevronDown, X, Store } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';
import { parseMenu } from '@/lib/api';
import { useAppContext } from '@/context/AppContext';

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

export default function UploadMenuPanel() {
  const router = useRouter();
  const { setParsedMenu, setRestaurant } = useAppContext();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [restaurantInput, setRestaurantInput] = useState('');
  const [targetLanguage, setTargetLanguage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = (file: File) => {
    setSelectedFile(file);
    setError(null);
    const url = URL.createObjectURL(file);
    setPreview(url);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith('image/')) {
      handleFile(file);
    }
  }, []);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const clearFile = () => {
    setSelectedFile(null);
    setPreview(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select a menu image first.');
      return;
    }
    setLoading(true);
    setError(null);

    try {
      const result = await parseMenu(selectedFile, targetLanguage);
      setParsedMenu(result, targetLanguage);
      // Store restaurant name so image fetching and ResultsHeader work
      if (restaurantInput.trim()) {
        setRestaurant({ place_id: '', name: restaurantInput.trim(), location: '' });
      }
      router.push('/results');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to parse menu. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 opacity-0 animate-fade-slide-up stagger-2">
      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !selectedFile && fileInputRef.current?.click()}
        className={cn(
          'relative rounded-2xl border-2 border-dashed transition-all duration-200',
          'flex flex-col items-center justify-center min-h-[200px]',
          isDragging
            ? 'border-primary bg-accent cursor-copy'
            : selectedFile
            ? 'border-border bg-card cursor-default'
            : 'border-border hover:border-primary/50 hover:bg-accent/50 cursor-pointer'
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileChange}
          className="sr-only"
        />

        {selectedFile && preview ? (
          <div className="relative w-full h-[200px] rounded-xl overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={preview}
              alt="Menu preview"
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-black/20" />
            <button
              onClick={(e) => { e.stopPropagation(); clearFile(); }}
              className="absolute top-3 right-3 flex items-center justify-center w-7 h-7 rounded-full bg-white/90 hover:bg-white text-foreground transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
            <div className="absolute bottom-3 left-3 right-3">
              <p className="text-white text-sm font-medium truncate drop-shadow">{selectedFile.name}</p>
              <p className="text-white/70 text-xs">{(selectedFile.size / 1024).toFixed(1)} KB</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 py-8 px-6 text-center">
            <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-accent text-primary">
              <FileImage className="w-7 h-7" strokeWidth={1.5} />
            </div>
            <div>
              <p className="font-medium text-foreground">Drop your menu image here</p>
              <p className="text-sm text-muted-foreground mt-0.5">or click to browse — JPG, PNG, HEIC supported</p>
            </div>
          </div>
        )}
      </div>

      {/* Restaurant name (optional) */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">
          Restaurant name <span className="text-muted-foreground">(optional)</span>
        </label>
        <div className="relative">
          <Store className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <input
            type="text"
            value={restaurantInput}
            onChange={(e) => setRestaurantInput(e.target.value)}
            placeholder="e.g. BCD Tofu House"
            className={cn(
              'w-full h-10 rounded-md border border-input bg-card pl-9 pr-3 text-sm',
              'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1',
              'text-foreground placeholder:text-muted-foreground/60 transition-colors duration-150',
            )}
          />
        </div>
        <p className="text-xs text-muted-foreground">Helps find dish photos and enables AI insights.</p>
      </div>

      {/* Language selector */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">
          Translate to <span className="text-muted-foreground">(optional)</span>
        </label>
        <div className="relative">
          <select
            value={targetLanguage ?? ''}
            onChange={(e) => setTargetLanguage(e.target.value === '' ? null : e.target.value)}
            className={cn(
              'w-full h-10 rounded-md border border-input bg-card px-3 pr-9 text-sm appearance-none',
              'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1',
              'text-foreground cursor-pointer transition-colors duration-150',
            )}
          >
            {SUPPORTED_LANGUAGES.map((lang) => (
              <option key={lang.code ?? 'none'} value={lang.code ?? ''}>
                {lang.name}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
        </div>
        <p className="text-xs text-muted-foreground">Menu language is detected automatically.</p>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Submit */}
      <Button
        onClick={handleUpload}
        disabled={!selectedFile || loading}
        size="lg"
        className="w-full font-medium gap-2"
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Analysing menu…
          </>
        ) : (
          <>
            <Upload className="w-4 h-4" />
            Parse Menu
          </>
        )}
      </Button>
    </div>
  );
}
