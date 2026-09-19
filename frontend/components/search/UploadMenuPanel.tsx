'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Upload, FileImage, Loader2, ChevronDown, X, Store, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';
import { parseMenu } from '@/lib/api';
import { useAppContext } from '@/context/AppContext';
import { keepMenuCopy, menuRecord, rememberMenu } from '@/lib/localHistory';

const SAMPLE_RESTAURANT = 'The Kroft';

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
  // The assistant links here with ?restaurant=… when a place's menu isn't available online,
  // so the name doesn't have to be typed again.
  const searchParams = useSearchParams();
  const { openMenu } = useAppContext();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [restaurantInput, setRestaurantInput] = useState(searchParams.get('restaurant') ?? '');
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

  // One-click demo path: load the bundled sample menu so reviewers don't need their own photo.
  // Its reading is seeded on the server, so it opens instantly and costs nothing.
  const sampleMenu = async () => {
    const response = await fetch('/sample-menu.png');
    const blob = await response.blob();
    return new File([blob], 'sample-menu.png', { type: blob.type || 'image/png' });
  };

  const loadSampleMenu = async () => {
    try {
      handleFile(await sampleMenu());
      setRestaurantInput(SAMPLE_RESTAURANT);
    } catch {
      setError('Could not load the sample menu.');
    }
  };

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
    await read(selectedFile, restaurantInput.trim() || null);
  };

  // The tour's first step lands here with ?demo=1: read the sample menu without asking anything.
  const demoStarted = useRef(false);
  useEffect(() => {
    if (searchParams.get('demo') !== '1' || demoStarted.current) return;
    demoStarted.current = true;
    router.replace('/search?mode=upload'); // Back or a refresh shouldn't run it again
    void sampleMenu()
      .then((file) => {
        handleFile(file);
        setRestaurantInput(SAMPLE_RESTAURANT);
        return read(file, SAMPLE_RESTAURANT);
      })
      .catch(() => setError('Could not load the sample menu.'));
    // Runs once, on arrival from the tour.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const read = async (file: File, restaurantName: string | null) => {
    setLoading(true);
    setError(null);

    try {
      const result = await parseMenu(file, targetLanguage, restaurantName);
      // The restaurant name scopes the dish photo search and titles the results page.
      openMenu(result, targetLanguage, restaurantName);
      if (result.menu_id) {
        rememberMenu({
          menuId: result.menu_id,
          label: restaurantName || `${result.detected_language ?? 'Parsed'} menu`,
          itemCount: result.menu.reduce((sum, category) => sum + category.items.length, 0),
          targetLanguage,
        });
        keepMenuCopy(menuRecord({ ...result, menu_id: result.menu_id }, restaurantName, targetLanguage));
      }
      // The menu id in the URL lets the results page survive a refresh.
      router.push(result.menu_id ? `/results?menu=${result.menu_id}` : '/results');
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

      {!selectedFile && (
        <button
          type="button"
          onClick={loadSampleMenu}
          className="w-full flex items-center justify-center gap-2 text-sm text-primary hover:underline"
        >
          <Sparkles className="w-4 h-4" />
          No menu handy? Try a sample menu
        </button>
      )}

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
