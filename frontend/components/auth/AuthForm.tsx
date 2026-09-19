'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/context/AuthContext';
import GoogleSignInButton from './GoogleSignInButton';

const USERNAME_PATTERN = /^[A-Za-z0-9_.-]{3,32}$/;

interface AuthFormProps {
  mode: 'login' | 'register';
}

export default function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, register } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isRegister = mode === 'register';
  // Only allow same-site relative redirects.
  const nextParam = searchParams.get('next');
  const next = nextParam?.startsWith('/') && !nextParam.startsWith('//') ? nextParam : '/';

  const validate = (): string | null => {
    if (isRegister) {
      if (!USERNAME_PATTERN.test(username)) {
        return 'Username must be 3–32 characters: letters, numbers, dot, dash or underscore.';
      }
      if (password.length < 8) return 'Password must be at least 8 characters.';
      if (password !== confirmPassword) return 'Passwords do not match.';
    } else if (!username || !password) {
      return 'Enter your username and password.';
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      if (isRegister) {
        await register(username, password);
      } else {
        await login(username, password);
      }
      router.push(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
      setSubmitting(false);
    }
  };

  const switchHref = `${isRegister ? '/login' : '/register'}${nextParam ? `?next=${encodeURIComponent(next)}` : ''}`;

  return (
    <form onSubmit={handleSubmit} className="space-y-5 opacity-0 animate-fade-slide-up stagger-2" noValidate>
      <GoogleSignInButton onSuccess={() => router.push(next)} onError={setError} />

      <div className="space-y-2">
        <label htmlFor="username" className="text-sm font-medium text-foreground">Username</label>
        <Input
          id="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="e.g. foodie_42"
        />
      </div>

      <div className="space-y-2">
        <label htmlFor="password" className="text-sm font-medium text-foreground">Password</label>
        <div className="relative">
          <Input
            id="password"
            type={showPassword ? 'text' : 'password'}
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="pr-10"
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        {isRegister && (
          <p className="text-xs text-muted-foreground">At least 8 characters.</p>
        )}
      </div>

      {isRegister && (
        <div className="space-y-2">
          <label htmlFor="confirm-password" className="text-sm font-medium text-foreground">Confirm password</label>
          <Input
            id="confirm-password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <Button type="submit" size="lg" className="w-full font-medium" disabled={submitting}>
        {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
        {isRegister ? 'Create account' : 'Sign in'}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        {isRegister ? 'Already have an account? ' : 'New to Menuist? '}
        <Link href={switchHref} className="text-primary hover:underline">
          {isRegister ? 'Sign in' : 'Create an account'}
        </Link>
      </p>
    </form>
  );
}
