import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { integrationsApi } from '@/services/endpoints/integrations';

export function useIntegrations() {
  return useQuery({
    queryKey: queryKeys.integrations.all(),
    queryFn:  integrationsApi.list,
    staleTime: 10 * 60 * 1000,  // integrations rarely change
    select: (data) => ({
      all:          data,
      connected:    data.filter(i => i.status === 'connected'),
      disconnected: data.filter(i => i.status === 'disconnected'),
      byCategory:   data.reduce((acc, i) => {
        if (!acc[i.category]) acc[i.category] = [];
        acc[i.category].push(i);
        return acc;
      }, {} as Record<string, typeof data>),
    }),
  });
}
