'use client';

import { useRef, type ReactNode } from 'react';
import {
  AlertCircle,
  Camera,
  CheckCircle2,
  Circle,
  Globe,
  Loader2,
  MessageSquareQuote,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';
import { useMenuSources } from '@/hooks/useMenuSources';
import type { SourceResult, SourceStatus } from '@/lib/api';
import type { LucideIcon } from 'lucide-react';

const STATUS_ICON: Record<SourceStatus, { icon: LucideIcon; className: string }> = {
  found: { icon: CheckCircle2, className: 'text-emerald-600' },
  none: { icon: Circle, className: 'text-muted-foreground/60' },
  unavailable: { icon: AlertCircle, className: 'text-amber-600' },
  error: { icon: XCircle, className: 'text-red-500' },
};

function SourceRow({
  icon: Icon,
  label,
  result,
  loading,
  fallback,
  action,
}: {
  icon: LucideIcon;
  label: string;
  result?: SourceResult;
  loading?: boolean;
  fallback?: string;
  action?: ReactNode;
}) {
  const status = result?.report.status;
  const Mark = loading ? Loader2 : status ? STATUS_ICON[status].icon : Circle;
  const trusted = result?.website_trusted !== false;

  return (
    <li className="flex items-start gap-3 py-2">
      <Mark
        className={cn(
          'mt-0.5 h-4 w-4 shrink-0',
          loading ? 'animate-spin text-primary' : status ? STATUS_ICON[status].className : 'text-muted-foreground/60'
        )}
      />
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <Icon className="h-3.5 w-3.5 text-muted-foreground" strokeWidth={1.75} />
          {label}
          {status === 'found' && (
            <span className="text-xs font-normal text-muted-foreground">· {result!.report.item_count} dishes</span>
          )}
        </p>
        <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
          {loading ? 'Checking…' : (result?.report.detail ?? fallback)}
          {result?.report.url && status === 'found' && trusted && (
            <>
              {' '}
              <a href={result.report.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                View source
              </a>
            </>
          )}
        </p>
      </div>
      {action}
    </li>
  );
}

/**
 * Where this restaurant's menu came from, source by source, and a way to add the real thing.
 *
 * No source stops the others: the website and the reviews each tend to have part of the menu, so
 * everything found is shown and labelled. Whether to add a photo is the diner's call —
 * the panel only says when the menu looks thin.
 */
export default function MenuSourcesPanel() {
  const { menuSources, checking, addPhotos, removePhotos, uploading, uploadError, reviewCount } = useMenuSources();
  const fileInput = useRef<HTMLInputElement>(null);

  if (!menuSources) return null;

  const combined = menuSources.combined;
  const stillChecking = checking.length > 0;
  const uploads = menuSources.uploads.length;
  const suggest = combined?.suggest_upload && !stillChecking;

  return (
    <section className="rounded-2xl border border-border bg-card px-5 py-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold text-foreground">Where this menu comes from</h2>
        {combined && (
          <span className="text-xs text-muted-foreground">
            {combined.total_items} dish{combined.total_items === 1 ? '' : 'es'}
            {stillChecking ? ' so far' : ''}
          </span>
        )}
      </div>

      <ul className="mt-2 divide-y divide-border/60">
        <SourceRow
          icon={Globe}
          label="Restaurant website"
          result={menuSources.website}
          loading={checking.includes('website')}
        />
        <SourceRow
          icon={MessageSquareQuote}
          label="Google reviews"
          result={{
            report: {
              kind: 'reviews',
              status: reviewCount ? 'found' : 'none',
              item_count: reviewCount,
              // Google shares only five reviews per place, which is why this is always a handful.
              detail: reviewCount
                ? 'Dishes named in the five reviews Google shares — a handful at most, not a menu.'
                : 'None of the five reviews Google shares names a dish.',
            },
          }}
        />
        {uploads > 0 && (
          <SourceRow
            icon={Camera}
            label="Your photos"
            result={{
              report: {
                kind: 'upload',
                status: 'found',
                item_count: menuSources.uploads.reduce(
                  (sum, source) => sum + source.menu.menu.reduce((n, category) => n + category.items.length, 0),
                  0
                ),
                detail: `Read from ${uploads} photo${uploads === 1 ? '' : 's'} you added — the freshest source, so its prices are shown first. Kept with this restaurant in your history.`,
              },
            }}
            action={
              <button
                type="button"
                onClick={removePhotos}
                className="shrink-0 text-xs text-muted-foreground hover:text-red-600 transition-colors"
              >
                Remove
              </button>
            }
          />
        )}
      </ul>

      <div
        className={cn(
          'mt-3 flex flex-col gap-3 rounded-xl px-4 py-3 sm:flex-row sm:items-center sm:justify-between',
          suggest ? 'bg-accent' : 'bg-muted/50'
        )}
      >
        <p className="text-xs leading-relaxed text-foreground/80">
          {stillChecking
            ? 'Still checking the restaurant’s website. You can add a photo of the menu any time.'
            : combined?.suggestion}
        </p>

        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(event) => {
            const files = Array.from(event.target.files ?? []);
            event.target.value = ''; // allow picking the same photo again
            void addPhotos(files);
          }}
        />
        <Button
          size="sm"
          variant={suggest ? 'default' : 'outline'}
          className="shrink-0 gap-1.5"
          disabled={uploading > 0}
          onClick={() => fileInput.current?.click()}
        >
          {uploading > 0 ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Camera className="h-3.5 w-3.5" />}
          {uploading > 0 ? `Reading ${uploading} photo${uploading === 1 ? '' : 's'}…` : uploads ? 'Add another page' : 'Add menu photos'}
        </Button>
      </div>

      {uploadError && <p className="mt-2 text-xs text-red-600">{uploadError}</p>}
    </section>
  );
}
