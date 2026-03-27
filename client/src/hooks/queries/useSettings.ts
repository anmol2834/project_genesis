import { useQuery } from '@tanstack/react-query';
import { settingsApi } from '@/services/endpoints/settings';
import { queryKeys } from '@/lib/react-query/queryKeys';

/**
 * Settings Query with Smart Caching & Real-time Updates
 * 
 * Features:
 * - 15 min staleTime: Settings don't change frequently
 * - 30 min gcTime: Keep in cache for fast navigation
 * - Automatic refetch on window focus disabled (cost optimization)
 * - Background refetch on mount if data is stale
 * - Shared cache across all components
 */

export function useUserSettings() {
  return useQuery({
    queryKey: queryKeys.settings.all(),
    queryFn: settingsApi.getSettings,
    staleTime: 15 * 60 * 1000,  // 15 minutes - settings rarely change
    gcTime: 30 * 60 * 1000,      // 30 minutes - keep in cache
    refetchOnWindowFocus: false, // Prevent unnecessary API calls
    refetchOnMount: 'always',    // Always check if stale on mount
  });
}
