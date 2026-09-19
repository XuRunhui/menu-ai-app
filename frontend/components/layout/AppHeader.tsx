'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import UserMenu from './UserMenu';

interface AppHeaderProps {
  showBack?: boolean;
  backHref?: string;
  hideUserMenu?: boolean;
  className?: string;
}

export default function AppHeader({ showBack = false, backHref, hideUserMenu = false, className }: AppHeaderProps) {
  const router = useRouter();

  const handleBack = () => {
    if (backHref) {
      router.push(backHref);
    } else {
      router.back();
    }
  };

  return (
    <header className={cn('w-full border-b border-border/60 bg-background/80 backdrop-blur-sm sticky top-0 z-40', className)}>
      <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
        {showBack ? (
          <button
            onClick={handleBack}
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors duration-150 group"
          >
            <ArrowLeft className="w-4 h-4 transition-transform duration-200 group-hover:-translate-x-0.5" />
            <span className="text-sm">Back</span>
          </button>
        ) : (
          <div className="w-10" />
        )}

        <Link
          href="/"
          className="font-display text-xl font-medium tracking-wide text-foreground hover:text-primary transition-colors duration-200"
        >
          Menuist
        </Link>

        {hideUserMenu ? <div className="w-10" /> : <UserMenu className="min-w-10 justify-end" />}
      </div>
    </header>
  );
}
