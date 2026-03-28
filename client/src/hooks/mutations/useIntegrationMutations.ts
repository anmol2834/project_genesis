import { useMutation, useQueryClient } from '@tanstack/react-query';
import { integrationsApi } from '@/services/endpoints/integrations';
import { queryKeys } from '@/lib/react-query/queryKeys';

export const useConnectIntegration = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: integrationsApi.connect,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
    },
  });
};

export const useDisconnectIntegration = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: integrationsApi.disconnect,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
    },
  });
};

export const useSyncIntegration = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: integrationsApi.sync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
    },
  });
};
