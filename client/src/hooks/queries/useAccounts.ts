import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { accountsApi } from '@/services/endpoints/accounts';
import type { EmailAccountFull } from '@/services/endpoints/email';

export function useAccounts() {
  return useQuery({
    queryKey: queryKeys.accounts.all(),
    queryFn:  accountsApi.list,
    staleTime: 2 * 60 * 1000, // 2 min — connection status can change
    select: (data: EmailAccountFull[]) => ({
      all:         data,
      connected:   data.filter(a => a.connection_status === 'connected'),
      error:       data.filter(a => a.connection_status === 'error'),
      active:      data.filter(a => a.is_active),
      gmail:       data.filter(a => a.provider === 'gmail'),
      outlook:     data.filter(a => a.provider === 'outlook'),
      smtp:        data.filter(a => a.provider === 'smtp'),
      totalSentToday: data.reduce((s, a) => s + a.daily_sent_count, 0),
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
