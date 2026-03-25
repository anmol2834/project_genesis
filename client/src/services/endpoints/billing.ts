import { get, post, patch } from '../apiClient';

export interface BillingPlan    { id: string; name: string; price: number; period: string; features: string[]; }
export interface Invoice         { id: string; date: string; amount: number; status: 'paid' | 'pending' | 'failed'; description: string; downloadUrl: string; }
export interface PaymentMethod   { id: string; brand: string; last4: string; expiry: string; isDefault: boolean; }
export interface UsageStat       { label: string; used: number; limit: number; unit: string; }
export interface BillingOverview { currentPlan: BillingPlan; usage: UsageStat[]; nextBillingDate: string; }

export const billingApi = {
  overview:        ()                          => get<BillingOverview>('/billing/overview'),
  invoices:        ()                          => get<Invoice[]>('/billing/invoices'),
  paymentMethods:  ()                          => get<PaymentMethod[]>('/billing/payment-methods'),
  changePlan:      (planId: string)            => post<BillingPlan>('/billing/change-plan', { planId }),
  addPaymentMethod:(token: string)             => post<PaymentMethod>('/billing/payment-methods', { token }),
  setDefault:      (pmId: string)              => patch<PaymentMethod>(`/billing/payment-methods/${pmId}/default`),
  cancelPlan:      ()                          => post<void>('/billing/cancel'),
};
