'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { History, LogOut, User } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { cn } from '@/lib/utils/cn';

export default function UserMenu({ className }: { className?: string }) {
  const { authEnabled, user, loading, logout } = useAuth();
  const pathname = usePathname();

  // Reserve space while the session check runs so the header doesn't jump.
  if (loading) return <div className={cn('w-16 h-8', className)} />;

  if (!authEnabled) {
    return (
      <Link
        href="/history"
        aria-label="History"
        title="Menus and restaurants opened on this device"
        className={cn('flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors', className)}
      >
        <History className="w-4 h-4" />
        <span className="hidden sm:inline">History</span>
      </Link>
    );
  }

  if (!user) {
    const next = pathname && pathname !== '/' ? `?next=${encodeURIComponent(pathname)}` : '';
    return (
      <Link
        href={`/login${next}`}
        className={cn('text-sm text-muted-foreground hover:text-foreground transition-colors', className)}
      >
        Sign in
      </Link>
    );
  }

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <Link
        href="/history"
        aria-label="History"
        title="Saved menus and restaurants"
        className="text-muted-foreground hover:text-foreground transition-colors"
      >
        <History className="w-4 h-4" />
      </Link>
      <span className="hidden sm:flex items-center gap-1.5 text-sm text-foreground">
        <User className="w-3.5 h-3.5 text-muted-foreground" />
        {user.username}
      </span>
      <button
        onClick={() => logout()}
        aria-label="Sign out"
        title="Sign out"
        className="text-muted-foreground hover:text-foreground transition-colors"
      >
        <LogOut className="w-4 h-4" />
      </button>
    </div>
  );
}
