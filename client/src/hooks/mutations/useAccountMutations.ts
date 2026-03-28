import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { accountsApi } from '@/services/endpoints/accounts';
import type { EmailAccountFull } from '@/services/endpoints/email';

export function useToggleAutomation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      accountsApi.update(id, { automation_enabled: enabled }),
    onMutate: async ({ id, enabled }) => {
      await qc.cancelQueries({ queryKey: queryKeys.accounts.all() });
      const prev = qc.getQueryData<EmailAccountFull[]>(queryKeys.accounts.all());
      qc.setQueryData<EmailAccountFull[]>(
        queryKeys.accounts.all(),
        old => old?.map(a => a.id === id ? { ...a, automation_enabled: enabled } : a),
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.accounts.all(), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.accounts.all() }),
  });
}

export function useToggleActive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      accountsApi.update(id, { is_active: active }),
    onMutate: async ({ id, active }) => {
      await qc.cancelQueries({ queryKey: queryKeys.accounts.all() });
      const prev = qc.getQueryData<EmailAccountFull[]>(queryKeys.accounts.all());
      qc.setQueryData<EmailAccountFull[]>(
        queryKeys.accounts.all(),
        old => old?.map(a => a.id === id ? { ...a, is_active: active } : a),
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
      await qc.cancelQueries({ queryKey: queryKeys.accounts.all() });
      const prev = qc.getQueryData<EmailAccountFull[]>(queryKeys.accounts.all());
      qc.setQueryData<EmailAccountFull[]>(
        queryKeys.accounts.all(),
        old => old?.filter(a => a.id !== id),
      );
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.accounts.all(), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.accounts.all() }),
  });
}
