import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { teamApi } from '@/services/endpoints/team';

export function useTeamMembers() {
  return useQuery({
    queryKey: queryKeys.team.members(),
    queryFn:  teamApi.list,
    staleTime: 5 * 60 * 1000,
    select: (data) => ({
      all:       data,
      active:    data.filter(m => m.status === 'active'),
      invited:   data.filter(m => m.status === 'invited'),
      suspended: data.filter(m => m.status === 'suspended'),
      owners:    data.filter(m => m.role === 'owner'),
      admins:    data.filter(m => m.role === 'admin'),
      members:   data.filter(m => m.role === 'member'),
    }),
  });
}

export function useTeamActivity() {
  return useQuery({
    queryKey: queryKeys.team.activity(),
    queryFn:  teamApi.activity,
    staleTime: 2 * 60 * 1000,
    refetchInterval: 2 * 60 * 1000, // activity feed refreshes every 2 min
  });
}
