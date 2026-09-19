import { Sparkles } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import type { DishContextResponse } from '@/lib/types';

interface DishLLMSummaryProps {
  loading: boolean;
  /** The flavor prediction is still on its way; the description shows meanwhile. */
  tagsLoading?: boolean;
  context: DishContextResponse | null;
  fallbackDescription?: string | null;
  /** Menu description in the chosen language, shown alongside the original. */
  translatedDescription?: string | null;
}

export default function DishLLMSummary({
  loading,
  tagsLoading = false,
  context,
  fallbackDescription,
  translatedDescription,
}: DishLLMSummaryProps) {
  if (loading) {
    return (
      <div className="space-y-3 py-2">
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
        <div className="flex gap-2 pt-2">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-6 w-16 rounded-full" />)}
        </div>
      </div>
    );
  }

  const description = context?.menu_description ?? fallbackDescription;
  // Refined with reviews when any mention the dish; otherwise read from the description alone.
  const prediction = context?.taste_texture?.round2 ?? context?.taste_texture?.round1;
  const flavorProfile = prediction?.flavor_profile;
  const tastes = prediction?.tastes ?? [];
  const textures = prediction?.textures ?? [];
  const allTags = [...tastes, ...textures];
  const metadata = context?.metadata;
  const hasMetadata = Boolean(
    metadata &&
      (metadata.price != null ||
        (metadata.spicy_level ?? 0) > 0 ||
        metadata.dietary_tags?.length ||
        metadata.allergens?.length)
  );

  const original = translatedDescription && translatedDescription !== description ? description : null;
  const primary = translatedDescription ?? description;

  if (!primary && allTags.length === 0 && !tagsLoading) return null;

  return (
    <div className="space-y-4">
      {primary && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-3.5 h-3.5 text-primary" />
            <span className="text-xs font-medium uppercase tracking-wider text-primary">
              {context?.menu_description ? 'AI Summary' : 'Description'}
            </span>
          </div>
          <p className="text-foreground leading-relaxed">
            {primary}
          </p>
          {original && (
            <p className="text-muted-foreground leading-relaxed mt-1.5">
              {original}
            </p>
          )}
        </div>
      )}

      {flavorProfile && (
        <blockquote className="border-l-2 border-primary/30 pl-4 italic text-muted-foreground text-sm leading-relaxed">
          {flavorProfile}
        </blockquote>
      )}

      {tagsLoading && (
        <div className="flex gap-2 pt-1" aria-label="Reading the flavors">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-6 w-16 rounded-full" />)}
        </div>
      )}

      {allTags.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-1">
          {tastes.map((taste) => (
            <Badge key={taste} variant="recommended" className="capitalize">
              {taste}
            </Badge>
          ))}
          {textures.map((texture) => (
            <Badge key={texture} variant="outline" className="capitalize text-muted-foreground">
              {texture}
            </Badge>
          ))}
        </div>
      )}

      {hasMetadata && metadata && (
        <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap pt-1">
          {metadata.price != null && (
            <span className="font-medium text-foreground">
              ${metadata.price.toFixed(2)}
            </span>
          )}
          {metadata.spicy_level != null && metadata.spicy_level > 0 && (
            <span>{'🌶️'.repeat(Math.min(metadata.spicy_level, 5))}</span>
          )}
          {metadata.dietary_tags?.map((tag) => (
            <span key={tag} className="capitalize">{tag}</span>
          ))}
          {metadata.allergens && metadata.allergens.length > 0 && (
            <span>Contains: {metadata.allergens.join(', ')}</span>
          )}
        </div>
      )}
    </div>
  );
}
