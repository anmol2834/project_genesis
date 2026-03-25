import { useMutation, useQueryClient } from '@tanstack/react-query';
import { researchEndpoints } from '@/services/endpoints/research';
import { queryKeys } from '@/lib/react-query/queryKeys';

export const useSaveResearch = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: researchEndpoints.save,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.research.all });
    },
  });
};

export const useDeleteResearch = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: researchEndpoints.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.research.all });
    },
  });
};
