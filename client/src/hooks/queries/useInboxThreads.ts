'use client';

import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { emailInboxApi, type InboxThread } from '@/services/endpoints/emailInbox';

const PAGE_SIZE = 10;

// ── Infinite threads (for the conversation list) ──────────────────────────────

export const INBOX_THREADS_KEY = ['inbox', 'email-threads'] as const;

export function useInboxThreads() {
  return useInfiniteQuery({
    queryKey:  INBOX_THREADS_KEY,
    queryFn:   ({ pageParam = 0 }) =>
      emailInboxApi.threads(PAGE_SIZE, pageParam as number),

    // React Query calls this to determine the next page's param.
    // Returns undefined when there are no more pages.
    // We use the total from the last page (backend always returns the real count).
    // fetched = sum of all threads loaded so far across all pages.
    getNextPageParam: (lastPage, allPages) => {
      const fetched = allPages.reduce((sum, p) => sum + p.threads.length, 0);
      // If we've loaded fewer threads than the total, there are more pages
      if (fetched < lastPage.total) return fetched;
      return undefined;
    },

    initialPageParam: 0,

    staleTime:            30 * 1000,
    gcTime:               30 * 60 * 1000,
    refetchInterval:      30 * 1000,
    refetchOnWindowFocus: true,
    refetchOnMount:       true,
    refetchOnReconnect:   true,
  });
}

// ── Single thread (for the chat view) ────────────────────────────────────────

export function useInboxThread(threadId: string | null) {
  return useQuery({
    queryKey:             ['inbox', 'email-thread', threadId],
    queryFn:              () => emailInboxApi.thread(threadId!),
    enabled:              !!threadId,
    staleTime:            30 * 1000,
    gcTime:               30 * 60 * 1000,
    refetchInterval:      30 * 1000,
    refetchOnWindowFocus: true,
    refetchOnMount:       true,
  });
}
