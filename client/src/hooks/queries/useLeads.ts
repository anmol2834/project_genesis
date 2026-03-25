import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { leadsApi, type LeadsListParams } from '@/services/endpoints/leads';

/** Paginated leads list — supports status filter + search */
export function useLeads(params: LeadsListParams = {}) {
  return useQuery({
    queryKey: queryKeys.leads.list(params),
    queryFn:  () => leadsApi.list(params),
    staleTime: 3 * 60 * 1000,
    placeholderData: (prev) => prev, // keeps previous page visible while loading next
  });
}

/** Infinite scroll variant — for future infinite list implementation */
export function useLeadsInfinite(params: Omit<LeadsListParams, 'page'> = {}) {
  return useInfiniteQuery({
    queryKey: [...queryKeys.leads.all(), 'infinite', params],
    queryFn:  ({ pageParam = 1 }) => leadsApi.list({ ...params, page: pageParam as number, limit: 20 }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const totalPages = Math.ceil(lastPage.total / (lastPage.limit || 20));
      return lastPage.page < totalPages ? lastPage.page + 1 : undefined;
    },
    staleTime: 3 * 60 * 1000,
  });
}

/** Single lead detail */
export function useLead(id: string) {
  return useQuery({
    queryKey: queryKeys.leads.detail(id),
    queryFn:  () => leadsApi.get(id),
    enabled:  !!id,
  });
}
