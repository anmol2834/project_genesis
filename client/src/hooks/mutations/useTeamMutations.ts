import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { teamApi, type InviteMemberPayload, type UpdateMemberPayload } from '@/services/endpoints/team';

export function useInviteMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: InviteMemberPayload) => teamApi.invite(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.team.members() }),
  });
}

export function useUpdateMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateMemberPayload }) =>
      teamApi.update(id, payload),
    onMutate: async ({ id, payload }) => {
      await qc.cancelQueries({ queryKey: queryKeys.team.members() });
      const prev = qc.getQueryData(queryKeys.team.members());
      qc.setQueryData<any[]>(queryKeys.team.members(), old =>
        old?.map(m => m.id === id ? { ...m, ...payload } : m));
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.team.members(), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.team.members() }),
  });
}

export function useRemoveMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => teamApi.remove(id),
    onMutate: async (id) => {
      const prev = qc.getQueryData(queryKeys.team.members());
      qc.setQueryData<any[]>(queryKeys.team.members(), old => old?.filter(m => m.id !== id));
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.team.members(), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.team.members() }),
  });
}
