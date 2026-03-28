import { useQuery } from '@tanstack/react-query';
import { profileApi } from '@/services/endpoints/profile';
import { queryKeys } from '@/lib/react-query/queryKeys';

/**
 * User Profile Query with Smart Caching
 * 
 * Features:
 * - 10 min staleTime: Profile data doesn't change frequently
 * - 30 min gcTime: Keep in cache for fast navigation
 * - Automatic refetch on mount if stale
 * - Shared cache across all components
 * - Syncs with AuthContext user data
 */

export function useUserProfile() {
  return useQuery({
    queryKey: queryKeys.profile.detail(),
    queryFn: profileApi.getProfile,
    staleTime: 10 * 60 * 1000,  // 10 minutes
    gcTime: 30 * 60 * 1000,      // 30 minutes
    refetchOnWindowFocus: false, // Prevent unnecessary API calls
    refetchOnMount: 'always',    // Always check if stale on mount
  });
}
