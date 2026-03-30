/**
 * Email Inbox API — real data from email-service via gateway.
 *
 * Gateway routes /email-service/* → email-service:8004
 * So /email-service/email/inbox/threads → email-service GET /email/inbox/threads
 */

import { get, post } from '../apiClient';

// ── Types ─────────────────────────────────────────────────────────────────────

/** A single message stored in last_24h_messages JSONB */
export interface InboxMessage {
  from:            string;
  to:              string[];
  content:         string;
  timestamp:       string;
  direction:       'incoming' | 'outgoing';
  has_attachments: boolean;
}

/** A conversation thread returned by the inbox API */
export interface InboxThread {
  id:              string;
  thread_id:       string;
  subject:         string;
  from_email:      string;
  to_emails:       string[];
  provider:        string;
  is_read:         boolean;
  status:          string;
  last_message_at: string | null;
  updated_at:      string | null;
  messages:        InboxMessage[];
  // Convenience fields
  snippet:         string;
  direction:       'incoming' | 'outgoing';
  unread:          number;
}

export interface ThreadsResponse {
  threads: InboxThread[];
  total:   number;
}

/** SSE event pushed by the server */
export interface InboxSSEEvent {
  type:      'new_message';
  thread_id: string;
  thread:    InboxThread;
}

// ── API calls ─────────────────────────────────────────────────────────────────

const BASE = '/email-service/email/inbox';

export const emailInboxApi = {
  /** Fetch all threads (initial load) */
  threads: (limit = 50, offset = 0) =>
    get<ThreadsResponse>(`${BASE}/threads`, { params: { limit, offset } }),

  /** Fetch a single thread */
  thread: (threadId: string) =>
    get<InboxThread>(`${BASE}/threads/${threadId}`),

  /** Mark thread as read */
  markRead: (threadId: string) =>
    post<{ status: string }>(`${BASE}/threads/${threadId}/read`),

  /** SSE stream URL — used directly with EventSource */
  streamUrl: () => `${BASE}/stream`,
};
