import { useQuery } from '@tanstack/react-query';
import { researchApi, type ResearchParams } from '@/services/endpoints/research';

export function useResearchHistory(params?: ResearchParams) {
  return useQuery({
    queryKey: ['research', 'history', params],
    queryFn:  () => researchApi.list(params),
    staleTime: 2 * 60 * 1000,
  });
}

export function useResearchQuery(id: string) {
  return useQuery({
    queryKey: ['research', id],
    queryFn:  () => researchApi.get(id),
    enabled:  !!id,
    // Poll until done — stops when status is 'done' or 'failed'
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'done' || status === 'failed' ? false : 3000;
    },
  });
}
