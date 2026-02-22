import { Sparkles } from 'lucide-react';

export default function ComboPlaceholder() {
  return (
    <div className="flex flex-col items-center justify-center gap-5 py-24 text-center opacity-0 animate-fade-slide-up stagger-1">
      <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-accent text-primary">
        <Sparkles className="w-7 h-7" strokeWidth={1.5} />
      </div>
      <div className="space-y-2">
        <h3 className="font-display text-2xl font-light text-foreground">
          Combo Recommendations
        </h3>
        <p className="text-muted-foreground text-sm max-w-sm leading-relaxed">
          Personalised dish pairings and combo suggestions powered by AI are on their way.
        </p>
      </div>
      <span className="inline-flex items-center rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
        Coming soon
      </span>
    </div>
  );
}
