import { useMutation, useQueryClient } from '@tanstack/react-query';
import { billingEndpoints } from '@/services/endpoints/billing';
import { queryKeys } from '@/lib/react-query/queryKeys';

export const useUpdateSubscription = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: billingEndpoints.updateSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.billing.subscription });
      queryClient.invalidateQueries({ queryKey: queryKeys.billing.usage });
    },
  });
};

export const useAddPaymentMethod = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: billingEndpoints.addPaymentMethod,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.billing.paymentMethods });
    },
  });
};

export const useRemovePaymentMethod = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: billingEndpoints.removePaymentMethod,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.billing.paymentMethods });
    },
  });
};
