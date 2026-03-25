import { useMutation, useQueryClient } from '@tanstack/react-query';
import { integrationEndpoints } from '@/services/endpoints/integrations';
import { queryKeys } from '@/lib/react-query/queryKeys';

export const useConnectIntegration = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: integrationEndpoints.connect,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations.all });
    },
  });
};

export const useDisconnectIntegration = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: integrationEndpoints.disconnect,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations.all });
    },
  });
};

export const useSyncIntegration = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: integrationEndpoints.sync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations.all });
    },
  });
};
