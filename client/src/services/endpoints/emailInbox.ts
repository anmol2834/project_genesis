/**
 * Email Inbox API — reads from es_messages + es_conversations via emailservice.
 *
 * Gateway routes /email-service/* → emailservice:8004
 * So /email-service/email/inbox/threads → emailservice GET /email/inbox/threads
 */

import { get, post } from '../apiClient';

// ── Types matching the actual emailservice inbox.py response ──────────────────

/** A single message from es_messages table */
export interface InboxMessage {
  message_id:      string;
  from_email:      string;
  to_emails:       string[];
  subject:         string | null;
  content:         string | null;
  timestamp:       string;
  direction:       'incoming' | 'outgoing';
  is_read:         boolean;
  has_attachments: boolean;
  // Draft & lifecycle
  draft_message:   string | null;
  message_state:   'received' | 'drafted' | 'queued' | 'sent' | 'failed' | null;
  // Aliases provided by backend for compatibility
  from:            string;
  to:              string[];
}

/** A conversation thread from es_conversations + es_messages */
export interface InboxThread {
  id:              string;
  thread_id:       string;
  subject:         string;
  provider:        string;
  is_read:         boolean;
  status:          string;
  last_message_at: string | null;
  message_count:   number;
  participants:    string[];
  // Fields populated by inbox.py _fmt_conv()
  from_email:      string;   // the "other party" email — never empty
  to_emails:       string[];
  unread:          number;
  snippet:         string;
  direction:       'incoming' | 'outgoing';
  // AI / lead fields
  priority_score:  number | null;
  intent_type:     string | null;
  lead_status:     string | null;
  tags:            string[];
  follow_up_required: boolean;
  messages:        InboxMessage[];
}

export interface ThreadsResponse {
  threads: InboxThread[];
  total:   number;
}

// ── API calls ─────────────────────────────────────────────────────────────────

const BASE = '/email-service/email/inbox';

export const emailInboxApi = {
  /** Fetch threads with pagination */
  threads: (limit = 10, offset = 0) =>
    get<ThreadsResponse>(`${BASE}/threads`, { params: { limit, offset } }),

  /** Fetch a single thread with all messages */
  thread: (threadId: string) =>
    get<InboxThread>(`${BASE}/threads/${threadId}`),

  /** Mark thread as read */
  markRead: (threadId: string) =>
    post<{ status: string }>(`${BASE}/threads/${threadId}/read`),

  /** Send a stored AI draft (user clicks "Send" on a pending draft) */
  sendDraft: (payload: { message_id: string; user_id: string; email_account_id: string }) =>
    post<{ success: boolean; provider_message_id?: string; sent_at: string; error?: string }>(
      '/email-service/email/send-draft', payload
    ),
};
