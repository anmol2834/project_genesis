'use client';

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { buildTheme, type ThemeMode } from './index';

// ─── Context ────────────────────────────────────────────────────────────────

interface ThemeContextValue {
  mode: ThemeMode;
  toggleTheme: () => void;
  setMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  mode: 'light',
  toggleTheme: () => {},
  setMode: () => {},
});

export const useThemeMode = () => useContext(ThemeContext);

// ─── Storage helpers ─────────────────────────────────────────────────────────

const STORAGE_KEY = 'pg-theme-mode';

function getInitialMode(): ThemeMode {
  if (typeof window === 'undefined') return 'light';
  const attr = document.documentElement.getAttribute('data-theme') as ThemeMode | null;
  if (attr === 'light' || attr === 'dark') return attr;
  const stored = localStorage.getItem(STORAGE_KEY) as ThemeMode | null;
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

// ─── Provider ────────────────────────────────────────────────────────────────

export function AppThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>('light');

  // Hydrate from localStorage / system preference after mount
  useEffect(() => {
    setModeState(getInitialMode());
  }, []);

  // Sync mode to DOM attributes, color-scheme, and document body styles
  useEffect(() => {
    const root = document.documentElement;
    const body = document.body;
    root.setAttribute('data-theme', mode);
    root.setAttribute('data-mui-color-scheme', mode);
    root.style.colorScheme = mode;
    const bg = mode === 'dark' ? '#080d18' : '#f8fafc';
    const fg = mode === 'dark' ? '#f8fafc' : '#0f172a';
    root.style.backgroundColor = bg;
    if (body) {
      body.style.backgroundColor = bg;
      body.style.color = fg;
    }
  }, [mode]);

  // Sync system preference changes
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => {
      if (!localStorage.getItem(STORAGE_KEY)) {
        setModeState(e.matches ? 'dark' : 'light');
      }
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next);
    localStorage.setItem(STORAGE_KEY, next);
  }, []);

  const toggleTheme = useCallback(() => {
    setMode(mode === 'light' ? 'dark' : 'light');
  }, [mode, setMode]);

  const theme = useMemo(() => buildTheme(mode), [mode]);

  const ctx = useMemo(() => ({ mode, toggleTheme, setMode }), [mode, toggleTheme, setMode]);

  return (
    <ThemeContext.Provider value={ctx}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ThemeContext.Provider>
  );
}
