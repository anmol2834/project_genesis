import { useMutation, useQueryClient } from '@tanstack/react-query';
import { researchApi } from '@/services/endpoints/research';

export const useSaveResearch = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (query: string) => researchApi.run(query),
    onSuccess: () => {
      // Invalidate research list if we add query keys for it later
    },
  });
};

export const useDeleteResearch = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: researchApi.delete,
    onSuccess: () => {
      // Invalidate research list if we add query keys for it later
    },
  });
};
