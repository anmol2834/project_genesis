import { useQuery } from '@tanstack/react-query';
import { settingsApi } from '@/services/endpoints/settings';

// Settings use simple string keys — no pagination or variants needed
export function useProfile() {
  return useQuery({
    queryKey: ['settings', 'profile'],
    queryFn:  settingsApi.profile,
    staleTime: 10 * 60 * 1000,
  });
}

export function useAiSettings() {
  return useQuery({
    queryKey: ['settings', 'ai'],
    queryFn:  settingsApi.aiSettings,
    staleTime: 10 * 60 * 1000,
  });
}

export function useNotificationSettings() {
  return useQuery({
    queryKey: ['settings', 'notifications'],
    queryFn:  settingsApi.notifications,
    staleTime: 10 * 60 * 1000,
  });
}
