import { useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsEndpoints } from '@/services/endpoints/settings';
import { queryKeys } from '@/lib/react-query/queryKeys';

export const useUpdateProfile = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: settingsEndpoints.updateProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.profile });
    },
  });
};

export const useUpdatePreferences = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: settingsEndpoints.updatePreferences,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.preferences });
    },
  });
};

export const useUpdateNotifications = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: settingsEndpoints.updateNotifications,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.notifications });
    },
  });
};
