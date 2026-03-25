import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { campaignsApi, type Campaign } from '@/services/endpoints/campaigns';

/** All campaigns list — 5 min stale, used on Campaigns page + Dashboard */
export function useCampaigns() {
  return useQuery({
    queryKey: queryKeys.campaigns.all(),
    queryFn:  campaignsApi.list,
    staleTime: 5 * 60 * 1000,
    select: (data: Campaign[]) => ({
      all:     data,
      running: data.filter(c => c.status === 'running'),
      paused:  data.filter(c => c.status === 'paused'),
      draft:   data.filter(c => c.status === 'draft'),
    }),
  });
}

/** Single campaign detail — prefetch on hover */
export function useCampaign(id: string) {
  return useQuery({
    queryKey: queryKeys.campaigns.detail(id),
    queryFn:  () => campaignsApi.get(id),
    enabled:  !!id,
    staleTime: 3 * 60 * 1000,
  });
}
