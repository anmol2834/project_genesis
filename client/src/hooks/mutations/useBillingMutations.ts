import { useMutation, useQueryClient } from '@tanstack/react-query';
import { billingApi } from '@/services/endpoints/billing';
import { queryKeys } from '@/lib/react-query/queryKeys';

export const useUpdateSubscription = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: billingApi.changePlan,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.billing.overview() });
    },
  });
};

export const useAddPaymentMethod = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: billingApi.addPaymentMethod,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.billing.paymentMethods() });
    },
  });
};

export const useRemovePaymentMethod = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (pmId: string) => billingApi.setDefault(pmId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.billing.paymentMethods() });
    },
  });
};
