import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { analyticsApi, type TimeRange } from '@/services/endpoints/analytics';

/**
 * Analytics overview — longer stale time since historical data rarely changes.
 * select: separates kpi and series so components can subscribe to only what they need.
 */
export function useAnalyticsOverview(range: TimeRange) {
  return useQuery({
    queryKey: queryKeys.analytics.overview(range),
    queryFn:  () => analyticsApi.overview(range),
    staleTime: 10 * 60 * 1000,   // 10 min — analytics data is expensive to compute
    gcTime:    60 * 60 * 1000,   // 1 hour — keep all 3 ranges cached simultaneously
  });
}

/** KPI strip only — lightweight select */
export function useAnalyticsKPI(range: TimeRange) {
  return useQuery({
    queryKey: queryKeys.analytics.overview(range),
    queryFn:  () => analyticsApi.overview(range),
    staleTime: 10 * 60 * 1000,
    select: (data) => data.kpi,
  });
}

/** Chart series only */
export function useAnalyticsSeries(range: TimeRange) {
  return useQuery({
    queryKey: queryKeys.analytics.overview(range),
    queryFn:  () => analyticsApi.overview(range),
    staleTime: 10 * 60 * 1000,
    select: (data) => data.series,
  });
}

export function useAnalyticsCampaigns() {
  return useQuery({
    queryKey: queryKeys.analytics.campaigns(),
    queryFn:  analyticsApi.campaigns,
    staleTime: 10 * 60 * 1000,
  });
}

export function useAnalyticsAccounts() {
  return useQuery({
    queryKey: queryKeys.analytics.accounts(),
    queryFn:  analyticsApi.accounts,
    staleTime: 10 * 60 * 1000,
  });
}
