/**
 * Protected Route Component
 * Wraps dashboard routes to ensure authentication
 */

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/sign-in');
    }
  }, [isAuthenticated, isLoading, router]);

  // Don't show loading screen - let dashboard render with skeleton loaders
  // Only redirect if not authenticated
  if (!isLoading && !isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
