'use client';

import { useQuery } from '@tanstack/react-query';
import { emailInboxApi } from '@/services/endpoints/emailInbox';

const THREADS_KEY = () => ['inbox', 'email-threads'] as const;

/**
 * useInboxThreads
 * Fetches all inbox threads on mount and polls every 30s.
 * User can also refresh the page to get the latest data.
 * No SSE/WebSocket — keeps Redis connection count low.
 */
export function useInboxThreads() {
  return useQuery({
    queryKey:             THREADS_KEY(),
    queryFn:              () => emailInboxApi.threads(),
    staleTime:            30 * 1000,        // 30s — refetch in background after this
    gcTime:               30 * 60 * 1000,   // 30 min in memory
    refetchInterval:      30 * 1000,        // poll every 30s
    refetchOnWindowFocus: true,             // refresh when user comes back to tab
    refetchOnMount:       true,
    refetchOnReconnect:   true,
    select: (data) => data.threads,
  });
}

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
