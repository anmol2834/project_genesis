import { useMutation, useQueryClient } from '@tanstack/react-query';
import { profileApi, type UserProfile, type UpdateProfileRequest, type UpdateProfileResponse } from '@/services/endpoints/profile';
import { queryKeys } from '@/lib/react-query/queryKeys';
import type { ApiError } from '@/services/apiClient';
import { useAuth } from '@/contexts/AuthContext';

/**
 * Profile Mutations with Optimistic Updates & Smart Invalidation
 * 
 * Features:
 * - Optimistic updates: UI updates immediately before API call completes
 * - Automatic rollback on error
 * - Smart cache invalidation: Invalidates profile and auth queries
 * - Syncs with AuthContext for consistent state
 * - Real-time UI feedback
 */

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  const { updateUser } = useAuth();

  return useMutation<UpdateProfileResponse, ApiError, UpdateProfileRequest>({
    mutationFn: profileApi.updateProfile,
    
    // Optimistic update: Update UI immediately
    onMutate: async (updatedData) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.profile.detail() });
      
      // Snapshot previous value
      const previousProfile = queryClient.getQueryData<UserProfile>(queryKeys.profile.detail());
      
      // Optimistically update cache
      if (previousProfile) {
        queryClient.setQueryData<UserProfile>(
          queryKeys.profile.detail(),
          { ...previousProfile, ...updatedData }
        );
      }
      
      // Also update AuthContext immediately for consistent state
      // Only update fields that are actually provided (not undefined)
      const authUpdate: Record<string, unknown> = {};
      if (updatedData.full_name !== undefined) authUpdate.full_name = updatedData.full_name;
      if (updatedData.business_name !== undefined) authUpdate.business_name = updatedData.business_name;
      if (updatedData.business_type !== undefined) authUpdate.business_type = updatedData.business_type;
      if (updatedData.industries !== undefined) authUpdate.industries = updatedData.industries;
      if (updatedData.country !== undefined) authUpdate.country = updatedData.country;
      if (updatedData.timezone !== undefined) authUpdate.timezone = updatedData.timezone;
      if (updatedData.business_description !== undefined) authUpdate.business_description = updatedData.business_description;
      if (updatedData.target_audience !== undefined) authUpdate.target_audience = updatedData.target_audience;
      if (updatedData.communication_tone !== undefined) authUpdate.communication_tone = updatedData.communication_tone;
      if (updatedData.use_cases !== undefined) authUpdate.use_cases = updatedData.use_cases;
      
      if (Object.keys(authUpdate).length > 0) {
        updateUser(authUpdate);
      }
      
      return { previousProfile };
    },
    
    // Rollback on error
    onError: (err, variables, context) => {
      if (context?.previousProfile) {
        queryClient.setQueryData(queryKeys.profile.detail(), context.previousProfile);
        
        // Rollback AuthContext - only update fields that were changed
        const authRollback: Record<string, unknown> = {};
        if (variables.full_name !== undefined) authRollback.full_name = context.previousProfile.full_name;
        if (variables.business_name !== undefined) authRollback.business_name = context.previousProfile.business_name;
        if (variables.business_type !== undefined) authRollback.business_type = context.previousProfile.business_type;
        if (variables.industries !== undefined) authRollback.industries = context.previousProfile.industries;
        if (variables.country !== undefined) authRollback.country = context.previousProfile.country;
        if (variables.timezone !== undefined) authRollback.timezone = context.previousProfile.timezone;
        if (variables.business_description !== undefined) authRollback.business_description = context.previousProfile.business_description;
        if (variables.target_audience !== undefined) authRollback.target_audience = context.previousProfile.target_audience;
        if (variables.communication_tone !== undefined) authRollback.communication_tone = context.previousProfile.communication_tone;
        if (variables.use_cases !== undefined) authRollback.use_cases = context.previousProfile.use_cases;
        
        if (Object.keys(authRollback).length > 0) {
          updateUser(authRollback);
        }
      }
    },
    
    // Always refetch after success to ensure server state is synced
    onSuccess: (data) => {
      // Update cache with server response
      queryClient.setQueryData(queryKeys.profile.detail(), data);
      
      // Sync AuthContext with server response - only update provided fields
      const authSync: Record<string, unknown> = {};
      if (data.full_name !== undefined) authSync.full_name = data.full_name;
      if (data.business_name !== undefined) authSync.business_name = data.business_name;
      if (data.business_type !== undefined) authSync.business_type = data.business_type;
      if (data.industries !== undefined) authSync.industries = data.industries;
      if (data.country !== undefined) authSync.country = data.country;
      if (data.timezone !== undefined) authSync.timezone = data.timezone;
      if (data.business_description !== undefined) authSync.business_description = data.business_description;
      if (data.target_audience !== undefined) authSync.target_audience = data.target_audience;
      if (data.communication_tone !== undefined) authSync.communication_tone = data.communication_tone;
      if (data.use_cases !== undefined) authSync.use_cases = data.use_cases;
      
      if (Object.keys(authSync).length > 0) {
        updateUser(authSync);
      }
      
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: queryKeys.profile.detail() });
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.me() });
    },
  });
}
