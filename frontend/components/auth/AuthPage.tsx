'use client';

import { Suspense } from 'react';
import Link from 'next/link';
import AppHeader from '@/components/layout/AppHeader';
import { useAuth } from '@/context/AuthContext';
import AuthForm from './AuthForm';

interface AuthPageProps {
  mode: 'login' | 'register';
}

export default function AuthPage({ mode }: AuthPageProps) {
  const isRegister = mode === 'register';
  const { authEnabled, loading } = useAuth();

  if (!loading && !authEnabled) {
    return (
      <main className="min-h-screen bg-background flex flex-col">
        <AppHeader showBack backHref="/" hideUserMenu />
        <div className="flex-1 max-w-sm mx-auto w-full px-6 py-16 space-y-3">
          <h1 className="font-display text-4xl font-light text-foreground">No account needed</h1>
          <p className="text-sm text-muted-foreground">
            This demo runs without sign-in; every feature works as a guest.{' '}
            <Link href="/" className="text-primary hover:underline">Back to the app</Link>
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background flex flex-col">
      <AppHeader showBack backHref="/" hideUserMenu />

      <div className="flex-1 max-w-sm mx-auto w-full px-6 py-16">
        <div className="mb-10 opacity-0 animate-fade-slide-up stagger-1">
          <p className="text-xs font-medium tracking-widest uppercase text-primary/70 mb-3">
            {isRegister ? 'Create account' : 'Welcome back'}
          </p>
          <h1 className="font-display text-4xl font-light text-foreground leading-tight">
            {isRegister ? 'Join Menuist' : 'Sign in'}
          </h1>
          <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
            {isRegister
              ? 'Pick a username and password to get started.'
              : 'Sign in with your username and password.'}
          </p>
        </div>

        {/* useSearchParams in AuthForm needs a Suspense boundary for static rendering */}
        <Suspense>
          <AuthForm mode={mode} />
        </Suspense>
      </div>
    </main>
  );
}
