import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { leadsApi, type Lead, type CreateLeadPayload } from '@/services/endpoints/leads';

export function useCreateLead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateLeadPayload) => leadsApi.create(payload),
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.leads.all() }),
  });
}

export function useUpdateLead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<Lead> }) =>
      leadsApi.update(id, payload),
    // Optimistic update on the detail cache
    onMutate: async ({ id, payload }) => {
      await qc.cancelQueries({ queryKey: queryKeys.leads.detail(id) });
      const prev = qc.getQueryData<Lead>(queryKeys.leads.detail(id));
      qc.setQueryData<Lead>(queryKeys.leads.detail(id), old => old ? { ...old, ...payload } : old);
      return { prev };
    },
    onError: (_err, { id }, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.leads.detail(id), ctx.prev);
    },
    onSettled: (_data, _err, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.leads.detail(id) });
      qc.invalidateQueries({ queryKey: queryKeys.leads.all() });
    },
  });
}

export function useDeleteLead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => leadsApi.delete(id),
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.leads.all() }),
  });
}

/**
 * CSV import — invalidates leads list after completion.
 * The loading state is handled by the CSVImportModal's own progress simulation;
 * this mutation fires the actual API call when the user confirms.
 */
export function useImportLeads() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (formData: FormData) => leadsApi.import(formData),
    onSuccess: () => {
      // Invalidate all lead list variants so the new leads appear
      qc.invalidateQueries({ queryKey: queryKeys.leads.all() });
    },
  });
}
