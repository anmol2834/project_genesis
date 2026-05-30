import { QueryClient } from '@tanstack/react-query';

/**
 * Global QueryClient — single instance for the entire app.
 *
 * Tuning rationale (Proxipilot):
 *  - staleTime 5 min: most dashboard data (leads, campaigns, analytics) doesn't
 *    change second-by-second. Avoids redundant background fetches on tab focus.
 *  - gcTime 30 min: keeps cached data in memory so navigating back to a page
 *    feels instant without a loading spinner.
 *  - retry 1: transient network errors get one retry; persistent errors surface fast.
 *  - refetchOnWindowFocus false: prevents a burst of API calls every time the user
 *    alt-tabs back — critical for cost optimization on a per-request billing model.
 *  - refetchOnReconnect true: when the user comes back online, stale data refreshes.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:            5 * 60 * 1000,   // 5 minutes
      gcTime:               30 * 60 * 1000,  // 30 minutes (formerly cacheTime)
      retry:                1,
      refetchOnWindowFocus: false,
      refetchOnReconnect:   true,
      refetchOnMount:       true,
    },
    mutations: {
      retry: 0, // mutations should not auto-retry — let the UI handle it
    },
  },
});
