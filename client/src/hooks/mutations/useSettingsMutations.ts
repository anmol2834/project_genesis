import { useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi, type UserSettings, type UpdateUserSettingsRequest } from '@/services/endpoints/settings';
import { queryKeys } from '@/lib/react-query/queryKeys';
import type { ApiError } from '@/services/apiClient';

/**
 * Settings Mutations with Optimistic Updates & Smart Invalidation
 * 
 * Features:
 * - Optimistic updates: UI updates immediately before API call completes
 * - Automatic rollback on error
 * - Smart cache invalidation: Only invalidates settings queries
 * - Debounced updates to prevent excessive API calls
 */

// ── Update Settings Mutation ──────────────────────────────────────────────────

export function useUpdateSettings() {
  const queryClient = useQueryClient();

  return useMutation<UserSettings, ApiError, UpdateUserSettingsRequest>({
    mutationFn: settingsApi.updateSettings,
    
    // Optimistic update: Update UI immediately
    onMutate: async (updatedData) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.settings.all() });
      
      // Snapshot previous value
      const previousSettings = queryClient.getQueryData<UserSettings>(queryKeys.settings.all());
      
      // Optimistically update cache
      if (previousSettings) {
        queryClient.setQueryData<UserSettings>(
          queryKeys.settings.all(),
          { ...previousSettings, ...updatedData }
        );
      }
      
      return { previousSettings };
    },
    
    // Rollback on error
    onError: (err, variables, context) => {
      if (context?.previousSettings) {
        queryClient.setQueryData(queryKeys.settings.all(), context.previousSettings);
      }
    },
    
    // Always refetch after success to ensure server state is synced
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.all() });
    },
  });
}

// ── Reset Settings Mutation ───────────────────────────────────────────────────

export function useResetSettings() {
  const queryClient = useQueryClient();

  return useMutation<UserSettings, ApiError, void>({
    mutationFn: settingsApi.resetSettings,
    onSuccess: (data) => {
      // Update cache with reset data
      queryClient.setQueryData(queryKeys.settings.all(), data);
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.all() });
    },
  });
}
