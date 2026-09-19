import { MessageSquareQuote } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';

interface DishReviewInsightProps {
  loading: boolean;
  excerpts: string[];
  reviewCount?: number;
}

export default function DishReviewInsight({ loading, excerpts, reviewCount }: DishReviewInsightProps) {
  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-4 w-1/4" />
        {[1, 2].map(i => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        ))}
      </div>
    );
  }

  const displayExcerpts = excerpts.slice(0, 3);

  if (displayExcerpts.length === 0) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <MessageSquareQuote className="w-3.5 h-3.5 text-primary" />
        <span className="text-xs font-medium uppercase tracking-wider text-primary">
          From {reviewCount ? `${reviewCount} ` : ''}Reviews
        </span>
      </div>

      <div className="space-y-3">
        {displayExcerpts.map((excerpt, idx) => (
          <blockquote
            key={idx}
            className="relative pl-4 py-2 text-sm text-muted-foreground leading-relaxed"
          >
            <span className="absolute left-0 top-0 bottom-0 w-0.5 rounded-full bg-border" />
            <span className="text-foreground/80 italic">"{excerpt}"</span>
          </blockquote>
        ))}
      </div>
    </div>
  );
}
