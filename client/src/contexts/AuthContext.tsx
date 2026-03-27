/**
 * Lightweight Auth Context - Client-Side State Management Only
 * 
 * Architecture:
 * - NO API calls (handled by React Query mutations)
 * - Only manages: user data, tokens, auth status
 * - Token storage in localStorage
 * - Route protection logic
 * - Auto token refresh scheduling
 * 
 * Separation of Concerns:
 * - React Query = Server state (API calls, loading, errors)
 * - AuthContext = Client state (user session, auth status)
 */

'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import type { User, TokenResponse } from '@/services/endpoints/auth';

// ─── Types ───────────────────────────────────────────────────────────────────

interface AuthContextType {
  // State
  user: User | null;
  tokens: TokenResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  
  // Actions
  setAuthData: (user: User, tokens: TokenResponse) => void;
  updateUser: (userData: Partial<User>) => void;
  updateTokens: (tokens: TokenResponse) => void;
  clearAuth: () => void;
  
  // Helpers
  getAccessToken: () => string | null;
  getRefreshToken: () => string | null;
  isTokenExpired: () => boolean;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const TOKEN_STORAGE_KEY = 'auth_tokens';
const USER_STORAGE_KEY = 'auth_user';
const TOKEN_EXPIRY_KEY = 'auth_token_expiry';

// Public routes that don't require authentication
const PUBLIC_ROUTES = ['/', '/sign-in', '/sign-up'];

// ─── Context ─────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ─── Provider ────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tokens, setTokens] = useState<TokenResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  // ─── Storage Helpers ───────────────────────────────────────────────────────

  const saveTokens = useCallback((authTokens: TokenResponse) => {
    try {
      localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(authTokens));
      
      // Calculate expiry timestamp
      const expiryTimestamp = Date.now() + (authTokens.expires_in * 1000);
      localStorage.setItem(TOKEN_EXPIRY_KEY, expiryTimestamp.toString());
      
      setTokens(authTokens);
    } catch (error) {
      console.error('[AuthContext] Failed to save tokens:', error);
    }
  }, []);

  const saveUser = useCallback((userData: User) => {
    try {
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(userData));
      setUser(userData);
    } catch (error) {
      console.error('[AuthContext] Failed to save user:', error);
    }
  }, []);

  const clearStorage = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(USER_STORAGE_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
    setTokens(null);
    setUser(null);
  }, []);

  // ─── Public Actions ────────────────────────────────────────────────────────

  const setAuthData = useCallback((userData: User, authTokens: TokenResponse) => {
    saveUser(userData);
    saveTokens(authTokens);
  }, [saveUser, saveTokens]);

  const updateUser = useCallback((userData: Partial<User>) => {
    setUser((prev) => {
      if (!prev) return null;
      const updated = { ...prev, ...userData };
      
      try {
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(updated));
      } catch (error) {
        console.error('[AuthContext] Failed to update user:', error);
      }
      
      return updated;
    });
  }, []);

  const updateTokens = useCallback((authTokens: TokenResponse) => {
    saveTokens(authTokens);
  }, [saveTokens]);

  const clearAuth = useCallback(() => {
    clearStorage();
  }, [clearStorage]);

  const getAccessToken = useCallback(() => {
    return tokens?.access_token ?? null;
  }, [tokens]);

  const getRefreshToken = useCallback(() => {
    return tokens?.refresh_token ?? null;
  }, [tokens]);

  const isTokenExpired = useCallback(() => {
    try {
      const expiryStr = localStorage.getItem(TOKEN_EXPIRY_KEY);
      if (!expiryStr) return true;
      
      const expiry = parseInt(expiryStr, 10);
      return Date.now() >= expiry;
    } catch {
      return true;
    }
  }, []);

  // ─── Computed State ────────────────────────────────────────────────────────

  const isAuthenticated = !!user && !!tokens;

  // ─── Initialize Auth State ─────────────────────────────────────────────────

  useEffect(() => {
    const initAuth = () => {
      try {
        const storedTokens = localStorage.getItem(TOKEN_STORAGE_KEY);
        const storedUser = localStorage.getItem(USER_STORAGE_KEY);

        if (!storedTokens || !storedUser) {
          setIsLoading(false);
          return;
        }

        const parsedTokens: TokenResponse = JSON.parse(storedTokens);
        const parsedUser: User = JSON.parse(storedUser);

        // Check if token is expired
        const expiryStr = localStorage.getItem(TOKEN_EXPIRY_KEY);
        if (expiryStr) {
          const expiry = parseInt(expiryStr, 10);
          if (Date.now() >= expiry) {
            // Token expired - clear auth
            clearStorage();
            setIsLoading(false);
            return;
          }
        }

        // Valid session - restore state immediately (synchronous)
        setTokens(parsedTokens);
        setUser(parsedUser);
        setIsLoading(false);
      } catch (error) {
        console.error('[AuthContext] Auth initialization failed:', error);
        clearStorage();
        setIsLoading(false);
      }
    };

    initAuth();
  }, [clearStorage]);

  // ─── Route Protection ──────────────────────────────────────────────────────

  useEffect(() => {
    if (isLoading) return;

    const isPublicRoute = PUBLIC_ROUTES.includes(pathname);
    const isDashboardRoute = pathname.startsWith('/dashboard');

    // Don't auto-redirect from signin/signup - they handle it with delay
    const isAuthPage = pathname === '/sign-in' || pathname === '/sign-up';
    
    // Redirect authenticated users away from home page only
    if (isAuthenticated && pathname === '/') {
      router.replace('/dashboard');
      return;
    }

    // Redirect unauthenticated users away from protected pages
    if (!isAuthenticated && isDashboardRoute) {
      router.replace('/sign-in');
      return;
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  // ─── Context Value ─────────────────────────────────────────────────────────

  const value: AuthContextType = {
    user,
    tokens,
    isAuthenticated,
    isLoading,
    setAuthData,
    updateUser,
    updateTokens,
    clearAuth,
    getAccessToken,
    getRefreshToken,
    isTokenExpired,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
