'use client';

import { useEffect, useRef, useState } from 'react';
import { getAuthConfig } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

interface GoogleCredentialResponse {
  credential: string;
}

interface GoogleIdentity {
  accounts: {
    id: {
      initialize: (options: { client_id: string; callback: (response: GoogleCredentialResponse) => void }) => void;
      renderButton: (element: HTMLElement, options: Record<string, string | number>) => void;
    };
  };
}

declare global {
  interface Window {
    google?: GoogleIdentity;
  }
}

const GIS_SCRIPT_SRC = 'https://accounts.google.com/gsi/client';

function loadGoogleScript(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GIS_SCRIPT_SRC}"]`);
    const script = existing ?? document.createElement('script');
    script.addEventListener('load', () => resolve());
    script.addEventListener('error', () => reject(new Error('Could not load Google sign-in')));
    if (!existing) {
      script.src = GIS_SCRIPT_SRC;
      script.async = true;
      document.head.appendChild(script);
    }
  });
}

interface GoogleSignInButtonProps {
  onSuccess: () => void;
  onError: (message: string) => void;
}

/** "Continue with Google" button. Renders nothing unless the backend has a Google client ID configured. */
export default function GoogleSignInButton({ onSuccess, onError }: GoogleSignInButtonProps) {
  const { loginWithGoogle } = useAuth();
  const [clientId, setClientId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Keep the latest callbacks without re-initializing Google's button on every render.
  const callbacks = useRef({ onSuccess, onError, loginWithGoogle });
  useEffect(() => {
    callbacks.current = { onSuccess, onError, loginWithGoogle };
  });

  useEffect(() => {
    getAuthConfig().then((config) => setClientId(config.google_client_id));
  }, []);

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;

    loadGoogleScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: async ({ credential }) => {
            try {
              await callbacks.current.loginWithGoogle(credential);
              callbacks.current.onSuccess();
            } catch (err) {
              callbacks.current.onError(err instanceof Error ? err.message : 'Google sign-in failed.');
            }
          },
        });
        window.google.accounts.id.renderButton(containerRef.current, {
          theme: 'outline',
          size: 'large',
          shape: 'pill',
          text: 'continue_with',
          width: 320,
        });
      })
      .catch((err: Error) => callbacks.current.onError(err.message));

    return () => { cancelled = true; };
  }, [clientId]);

  if (!clientId) return null;

  return (
    <div className="space-y-5">
      <div ref={containerRef} className="flex justify-center min-h-[44px]" />
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        or
        <span className="h-px flex-1 bg-border" />
      </div>
    </div>
  );
}
