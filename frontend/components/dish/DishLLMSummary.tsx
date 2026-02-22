import { Sparkles } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import type { DishContextResponse } from '@/lib/types';

interface DishLLMSummaryProps {
  loading: boolean;
  context: DishContextResponse | null;
  fallbackDescription?: string | null;
}

export default function DishLLMSummary({ loading, context, fallbackDescription }: DishLLMSummaryProps) {
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
  const flavorProfile = context?.taste_texture?.round2?.flavor_profile;
  const tastes = context?.taste_texture?.round2?.tastes ?? [];
  const textures = context?.taste_texture?.round2?.textures ?? [];
  const allTags = [...tastes, ...textures];

  if (!description && allTags.length === 0) return null;

  return (
    <div className="space-y-4">
      {description && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-3.5 h-3.5 text-primary" />
            <span className="text-xs font-medium uppercase tracking-wider text-primary">
              {context?.menu_description ? 'AI Summary' : 'Description'}
            </span>
          </div>
          <p className="text-foreground leading-relaxed">
            {description}
          </p>
        </div>
      )}

      {flavorProfile && (
        <blockquote className="border-l-2 border-primary/30 pl-4 italic text-muted-foreground text-sm leading-relaxed">
          {flavorProfile}
        </blockquote>
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

      {context?.metadata && (
        <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap pt-1">
          {context.metadata.price != null && (
            <span className="font-medium text-foreground">
              ${context.metadata.price.toFixed(2)}
            </span>
          )}
          {context.metadata.spicy_level != null && context.metadata.spicy_level > 0 && (
            <span>{'🌶️'.repeat(Math.min(context.metadata.spicy_level, 5))}</span>
          )}
          {context.metadata.dietary_tags?.map((tag) => (
            <span key={tag} className="capitalize">{tag}</span>
          ))}
          {context.metadata.allergens && context.metadata.allergens.length > 0 && (
            <span>Contains: {context.metadata.allergens.join(', ')}</span>
          )}
        </div>
      )}
    </div>
  );
}
