import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

type Theme = 'light' | 'dark';
type ThemeMode = Theme | 'auto';

interface ThemeContextValue {
    // Effective theme applied to the DOM
    theme: Theme;
    // Current mode (light, dark, or auto)
    mode: ThemeMode;
    setMode: (m: ThemeMode) => void;
    toggleMode: () => void; // cycles light -> dark -> auto
    // Back-compat helpers
    setTheme: (t: Theme) => void;
    toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function getInitialMode(): ThemeMode {
    try {
        const stored = localStorage.getItem('themeMode');
        if (stored === 'light' || stored === 'dark' || stored === 'auto') return stored;
    } catch {
        // ignore
    }
    return 'auto';
}

function getSystemTheme(): Theme {
    if (typeof window !== 'undefined' && window.matchMedia) {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return 'light';
}

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [mode, setMode] = useState<ThemeMode>(getInitialMode);
    const [systemTheme, setSystemTheme] = useState<Theme>(getSystemTheme);

    // Listen to system preference when in auto
        useEffect(() => {
            if (!window.matchMedia) return;
            const mq = window.matchMedia('(prefers-color-scheme: dark)');
            const handler = () => setSystemTheme(mq.matches ? 'dark' : 'light');
            // Modern browsers
            if (typeof mq.addEventListener === 'function') {
                mq.addEventListener('change', handler);
                return () => mq.removeEventListener('change', handler);
            }
            // Older Safari
            const anyMq = mq as unknown as { addListener?: (cb: () => void) => void; removeListener?: (cb: () => void) => void };
            anyMq.addListener?.(handler);
            return () => anyMq.removeListener?.(handler);
        }, []);

    const effectiveTheme: Theme = mode === 'auto' ? systemTheme : mode;

    // Apply to DOM and persist mode
    useEffect(() => {
        document.documentElement.setAttribute('data-bs-theme', effectiveTheme);
        try {
            localStorage.setItem('themeMode', mode);
        } catch {
            // ignore
        }
    }, [mode, effectiveTheme]);

    const value = useMemo<ThemeContextValue>(() => ({
        theme: effectiveTheme,
        mode,
        setMode,
        toggleMode: () => setMode((m) => (m === 'light' ? 'dark' : m === 'dark' ? 'auto' : 'light')),
        // Back-compat
        setTheme: (t: Theme) => setMode(t),
        toggleTheme: () => setMode((m) => (m === 'dark' ? 'light' : 'dark')),
    }), [effectiveTheme, mode]);

    return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export function useTheme(): ThemeContextValue {
    const ctx = useContext(ThemeContext);
    if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
    return ctx;
}
