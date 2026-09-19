'use client';

import Link from 'next/link';
import { type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils/cn';

interface EntryCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  href?: string;
  disabled?: boolean;
  className?: string;
  onClick?: () => void;
}

export default function EntryCard({
  icon: Icon,
  title,
  description,
  href,
  disabled = false,
  className,
  onClick,
}: EntryCardProps) {
  const inner = (
    <div
      className={cn(
        'group relative flex flex-col items-start gap-4 p-8 rounded-2xl border border-border bg-card',
        'transition-all duration-300 ease-out',
        !disabled && 'hover:border-primary/40 hover:shadow-[0_8px_30px_rgba(184,92,56,0.10)] hover:-translate-y-1 cursor-pointer',
        disabled && 'opacity-50 cursor-not-allowed select-none',
        className
      )}
    >
      {disabled && (
        <span className="absolute top-4 right-4 inline-flex items-center rounded-full border border-border px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
          Coming Soon
        </span>
      )}

      <div className={cn(
        'flex items-center justify-center w-12 h-12 rounded-xl',
        'bg-accent text-primary transition-all duration-300',
        !disabled && 'group-hover:bg-primary group-hover:text-primary-foreground group-hover:scale-105',
      )}>
        <Icon className="w-6 h-6" strokeWidth={1.5} />
      </div>

      <div className="space-y-1.5">
        <h3 className="font-display text-2xl font-semibold leading-tight text-foreground">
          {title}
        </h3>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {description}
        </p>
      </div>

      {!disabled && (
        <div className="mt-auto flex items-center gap-1 text-xs font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity duration-200">
          <span>Get started</span>
          <svg className="w-3 h-3 transition-transform duration-200 group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </div>
      )}
    </div>
  );

  if (disabled) return inner;

  if (onClick) {
    return (
      <button className="text-left w-full" onClick={onClick} disabled={disabled}>
        {inner}
      </button>
    );
  }

  return <Link href={href ?? '#'}>{inner}</Link>;
}
