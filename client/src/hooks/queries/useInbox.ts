import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { inboxApi, type ConversationsParams } from '@/services/endpoints/inbox';

/**
 * Conversations list.
 * refetchInterval: 60s background polling for real-time-like inbox updates
 * (SSE/WebSocket disabled for cost optimization per architecture docs).
 */
export function useConversations(params?: ConversationsParams) {
  return useQuery({
    queryKey: queryKeys.inbox.conversations(params),
    queryFn:  () => inboxApi.conversations(params),
    staleTime: 30 * 1000,          // 30s — inbox data is more time-sensitive
    refetchInterval: 60 * 1000,    // background poll every 60s
    select: (data) => ({
      all:       data,
      unread:    data.filter(c => c.unread > 0),
      aiHandled: data.filter(c => c.aiHandled),
      replied:   data.filter(c => c.status === 'replied'),
    }),
  });
}

/** Single thread — fetched when user opens a conversation */
export function useThread(threadId: string) {
  return useQuery({
    queryKey: queryKeys.inbox.thread(threadId),
    queryFn:  () => inboxApi.thread(threadId),
    enabled:  !!threadId,
    staleTime: 30 * 1000,
    refetchInterval: 30 * 1000,   // poll active thread every 30s
  });
}
