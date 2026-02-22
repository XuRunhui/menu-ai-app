import { cn } from '@/lib/utils/cn';

interface DishHeroProps {
  name: string;
  photoUrl?: string | null;
}

function getHeroGradient(name: string): string {
  const gradients = [
    'from-amber-100 via-orange-50 to-rose-50',
    'from-rose-100 via-pink-50 to-orange-50',
    'from-emerald-100 via-teal-50 to-cyan-50',
    'from-sky-100 via-blue-50 to-violet-50',
    'from-violet-100 via-purple-50 to-pink-50',
    'from-lime-100 via-green-50 to-emerald-50',
    'from-orange-100 via-amber-50 to-yellow-50',
    'from-cyan-100 via-sky-50 to-blue-50',
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i);
    hash |= 0;
  }
  return gradients[Math.abs(hash) % gradients.length];
}

export default function DishHero({ name, photoUrl }: DishHeroProps) {
  const initial = name.charAt(0).toUpperCase();
  const gradient = getHeroGradient(name);

  return (
    <div className="relative w-full h-64 md:h-80 overflow-hidden">
      {photoUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={photoUrl}
          alt={name}
          className="w-full h-full object-cover"
        />
      ) : (
        <div className={cn(
          'w-full h-full bg-gradient-to-br flex items-center justify-center',
          gradient,
        )}>
          <span className="font-display text-9xl font-light text-foreground/10 select-none">
            {initial}
          </span>
        </div>
      )}

      {/* Gradient overlay for text legibility */}
      <div className="absolute inset-0 bg-gradient-to-t from-background/80 via-transparent to-transparent" />

      {/* Dish name over image */}
      <div className="absolute bottom-0 left-0 right-0 px-6 pb-6">
        <h1 className="font-display text-4xl md:text-5xl font-light text-foreground leading-tight">
          {name}
        </h1>
      </div>
    </div>
  );
}
