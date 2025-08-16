import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

type AuthContextValue = {
  username: string;
  login: (name: string) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const STORAGE_KEY = 'username';
const MAX_LEN = 40;
const DEFAULT_USERNAME = 'guest'; // Default username when none is set
const allowed = /^[A-Za-z0-9._-]{1,40}$/;

function sanitize(name: string): string | null {
  const v = name.trim();
  if (!v || v.length > MAX_LEN) return null;
  if (!allowed.test(v)) return null;
  return v;
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) setUsername(stored);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    try {
      if (username) localStorage.setItem(STORAGE_KEY, username);
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }, [username]);

  const value = useMemo(
    () => ({
      username: username || DEFAULT_USERNAME, // Use default when username is null
      login: (name: string) => {
        const clean = sanitize(name);
        if (!clean) return;
        setUsername(clean);
      },
      logout: () => setUsername(null),
    }),
    [username]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
