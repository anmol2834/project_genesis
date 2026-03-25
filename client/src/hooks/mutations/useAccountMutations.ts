import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { accountsApi, type ConnectOAuthPayload, type ConnectSmtpPayload } from '@/services/endpoints/accounts';

export function useConnectOAuth() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ConnectOAuthPayload) => accountsApi.connectOAuth(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.accounts.all() }),
  });
}

export function useConnectSmtp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ConnectSmtpPayload) => accountsApi.connectSmtp(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.accounts.all() }),
  });
}

export function useToggleAutomation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      accountsApi.toggleAuto(id, enabled),
    // Optimistic toggle
    onMutate: async ({ id, enabled }) => {
      await qc.cancelQueries({ queryKey: queryKeys.accounts.all() });
      const prev = qc.getQueryData(queryKeys.accounts.all());
      qc.setQueryData<ReturnType<typeof accountsApi.list> extends Promise<infer T> ? T : never>(
        queryKeys.accounts.all(),
        (old: any) => old?.map((a: any) => a.id === id ? { ...a, automationEnabled: enabled } : a),
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.accounts.all(), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.accounts.all() }),
  });
}

export function useSyncAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => accountsApi.sync(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.accounts.all() }),
  });
}

export function useDeleteAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => accountsApi.delete(id),
    onMutate: async (id) => {
      const prev = qc.getQueryData(queryKeys.accounts.all());
      qc.setQueryData<any[]>(queryKeys.accounts.all(), old => old?.filter(a => a.id !== id));
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.accounts.all(), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.accounts.all() }),
  });
}
