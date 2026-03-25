import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { billingApi } from '@/services/endpoints/billing';

export function useBillingOverview() {
  return useQuery({
    queryKey: queryKeys.billing.overview(),
    queryFn:  billingApi.overview,
    staleTime: 10 * 60 * 1000,
  });
}

export function useInvoices() {
  return useQuery({
    queryKey: queryKeys.billing.invoices(),
    queryFn:  billingApi.invoices,
    staleTime: 30 * 60 * 1000,  // invoices are static historical data
  });
}

export function usePaymentMethods() {
  return useQuery({
    queryKey: queryKeys.billing.paymentMethods(),
    queryFn:  billingApi.paymentMethods,
    staleTime: 10 * 60 * 1000,
  });
}
