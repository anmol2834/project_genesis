import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { campaignsApi, type Campaign, type CreateCampaignPayload, type UpdateCampaignPayload } from '@/services/endpoints/campaigns';

export function useCreateCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateCampaignPayload) => campaignsApi.create(payload),
    // Optimistic: add a placeholder immediately
    onMutate: async (payload) => {
      await qc.cancelQueries({ queryKey: queryKeys.campaigns.all() });
      const prev = qc.getQueryData<Campaign[]>(queryKeys.campaigns.all());
      const optimistic: Campaign = {
        id: `temp-${Date.now()}`, name: payload.name, status: 'draft',
        emailsSent: 0, emailsTotal: payload.emailsTotal ?? 0,
        openRate: 0, replyRate: 0, lastActivity: 'Just now',
        createdAt: new Date().toLocaleDateString(), accentColor: '#818cf8',
        aiInsight: '', insightType: 'neutral', tags: payload.tags ?? [],
      };
      qc.setQueryData<Campaign[]>(queryKeys.campaigns.all(), old => [...(old ?? []), optimistic]);
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.campaigns.all(), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.campaigns.all() }),
  });
}

export function useUpdateCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateCampaignPayload }) =>
      campaignsApi.update(id, payload),
    onMutate: async ({ id, payload }) => {
      await qc.cancelQueries({ queryKey: queryKeys.campaigns.detail(id) });
      const prev = qc.getQueryData<Campaign>(queryKeys.campaigns.detail(id));
      qc.setQueryData<Campaign>(queryKeys.campaigns.detail(id), old => old ? { ...old, ...payload } : old);
      return { prev };
    },
    onError: (_err, { id }, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.campaigns.detail(id), ctx.prev);
    },
    onSettled: (_data, _err, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.campaigns.detail(id) });
      qc.invalidateQueries({ queryKey: queryKeys.campaigns.all() });
    },
  });
}

export function useDeleteCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => campaignsApi.delete(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: queryKeys.campaigns.all() });
      const prev = qc.getQueryData<Campaign[]>(queryKeys.campaigns.all());
      qc.setQueryData<Campaign[]>(queryKeys.campaigns.all(), old => old?.filter(c => c.id !== id));
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.campaigns.all(), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.campaigns.all() }),
  });
}

export function usePauseCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => campaignsApi.pause(id),
    onMutate: async (id) => {
      const prev = qc.getQueryData<Campaign[]>(queryKeys.campaigns.all());
      qc.setQueryData<Campaign[]>(queryKeys.campaigns.all(), old =>
        old?.map(c => c.id === id ? { ...c, status: 'paused' as const } : c));
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.campaigns.all(), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.campaigns.all() }),
  });
}

export function useResumeCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => campaignsApi.resume(id),
    onMutate: async (id) => {
      const prev = qc.getQueryData<Campaign[]>(queryKeys.campaigns.all());
      qc.setQueryData<Campaign[]>(queryKeys.campaigns.all(), old =>
        old?.map(c => c.id === id ? { ...c, status: 'running' as const } : c));
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.campaigns.all(), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.campaigns.all() }),
  });
}
