import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/queryKeys';
import { inboxApi, type Message, type SendReplyPayload, type Conversation } from '@/services/endpoints/inbox';

/**
 * Send reply — optimistic update appends the message to the thread immediately.
 * If the server call fails, the optimistic message is rolled back.
 */
export function useSendReply() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SendReplyPayload) => inboxApi.sendReply(payload),
    onMutate: async (payload) => {
      const key = queryKeys.inbox.thread(payload.threadId);
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<Conversation>(key);

      const optimisticMsg: Message = {
        id:        `temp-${Date.now()}`,
        sender:    'me',
        content:   payload.content,
        timestamp: new Date().toISOString(),
        isAI:      false,
      };

      qc.setQueryData<Conversation>(key, old =>
        old ? { ...old, messages: [...old.messages, optimisticMsg] } : old);

      return { prev };
    },
    onError: (_err, payload, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.inbox.thread(payload.threadId), ctx.prev);
    },
    onSettled: (_data, _err, payload) => {
      qc.invalidateQueries({ queryKey: queryKeys.inbox.thread(payload.threadId) });
      qc.invalidateQueries({ queryKey: queryKeys.inbox.all() });
    },
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (threadId: string) => inboxApi.markRead(threadId),
    onMutate: async (threadId) => {
      // Optimistically zero the unread count
      qc.setQueryData<Conversation[]>(queryKeys.inbox.conversations(), old =>
        old?.map(c => c.id === threadId ? { ...c, unread: 0 } : c));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.inbox.all() }),
  });
}
