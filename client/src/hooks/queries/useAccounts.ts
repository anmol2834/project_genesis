import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { accountsApi } from '@/services/endpoints/accounts';

/** All connected email accounts */
export function useAccounts() {
  return useQuery({
    queryKey: queryKeys.accounts.all(),
    queryFn:  accountsApi.list,
    staleTime: 5 * 60 * 1000,
    select: (data) => ({
      all:       data,
      connected: data.filter(a => a.status === 'connected'),
      syncing:   data.filter(a => a.status === 'syncing'),
      paused:    data.filter(a => a.status === 'paused'),
      gmail:     data.filter(a => a.provider === 'gmail'),
      outlook:   data.filter(a => a.provider === 'outlook'),
    }),
  });
}

export function useAccount(id: string) {
  return useQuery({
    queryKey: queryKeys.accounts.detail(id),
    queryFn:  () => accountsApi.get(id),
    enabled:  !!id,
  });
}
