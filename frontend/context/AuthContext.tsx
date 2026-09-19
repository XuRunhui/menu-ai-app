'use client';

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import {
  getAuthConfig,
  getCurrentUser,
  loginUser,
  loginWithGoogleCredential,
  logoutUser,
  registerUser,
  type AuthUser,
} from '@/lib/api';

interface AuthContextValue {
  /** False in guest-only mode: no sign-in UI, everything works without an account. */
  authEnabled: boolean;
  user: AuthUser | null;
  /** True until the initial session check finishes. */
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [authEnabled, setAuthEnabled] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const config = await getAuthConfig();
      const current = config.auth_enabled ? await getCurrentUser() : null;
      if (!cancelled) {
        setAuthEnabled(config.auth_enabled);
        setUser(current);
        setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setUser(await loginUser(username, password));
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    setUser(await registerUser(username, password));
  }, []);

  const loginWithGoogle = useCallback(async (credential: string) => {
    setUser(await loginWithGoogleCredential(credential));
  }, []);

  const logout = useCallback(async () => {
    await logoutUser();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ authEnabled, user, loading, login, register, loginWithGoogle, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
