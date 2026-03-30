/**
 * inboxAdapter.ts
 * Maps InboxThread (backend shape) → Conversation (UI shape).
 *
 * The existing ChatView and ConversationList components use the Conversation
 * interface from inboxData.ts. This adapter bridges the two without touching
 * the UI components' internal logic.
 */

import type { InboxThread, InboxMessage } from '@/services/endpoints/emailInbox';
import type { Conversation, Message, LeadTag } from './inboxData';

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Derive display name from email address: "john.doe@example.com" → "John Doe" */
function nameFromEmail(email: string): string {
  const local = email.split('@')[0] ?? email;
  return local
    .replace(/[._-]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

/** Two-letter initials from a display name */
function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

/** Deterministic avatar color from a string */
const AVATAR_COLORS = [
  '#818cf8', '#c084fc', '#22d3ee', '#34d399',
  '#fbbf24', '#f472b6', '#fb923c', '#a3e635',
];
function avatarColor(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

/** Relative time string from ISO timestamp */
function relativeTime(iso: string | null): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1)  return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

/** Format ISO timestamp to "HH:MM AM/PM" */
function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

/** Map backend direction to UI role */
function toRole(direction: 'incoming' | 'outgoing'): 'received' | 'sent' {
  return direction === 'outgoing' ? 'sent' : 'received';
}

/** Assign a lead tag based on unread count / recency (heuristic — no lead scoring yet) */
function inferLeadTag(thread: InboxThread): LeadTag {
  if (thread.unread > 0) return 'hot';
  const lastAt = thread.last_message_at ? new Date(thread.last_message_at).getTime() : 0;
  const hoursAgo = (Date.now() - lastAt) / 3_600_000;
  if (hoursAgo < 6)  return 'warm';
  return 'cold';
}

// ── Main adapter ──────────────────────────────────────────────────────────────

export function threadToConversation(thread: InboxThread): Conversation {
  const senderEmail = thread.from_email || 'unknown@email.com';
  const displayName = nameFromEmail(senderEmail);
  const tag         = inferLeadTag(thread);

  // Sort messages by timestamp ASC (oldest first — chat order)
  const sorted = [...(thread.messages ?? [])].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  const messages: Message[] = sorted.map((m: InboxMessage, idx) => ({
    id:     `${thread.thread_id}-${idx}`,
    role:   toRole(m.direction),
    text:   m.content,
    time:   formatTime(m.timestamp),
    status: m.direction === 'outgoing' ? 'read' : undefined,
  }));

  const latestMsg = sorted[sorted.length - 1];

  return {
    id:          thread.thread_id,          // use thread_id as stable key
    name:        displayName,
    email:       senderEmail,
    avatar:      initials(displayName),
    avatarColor: avatarColor(senderEmail),
    subject:     thread.subject,
    snippet:     thread.snippet || latestMsg?.content?.slice(0, 80) || '',
    time:        relativeTime(thread.last_message_at),
    unread:      thread.unread,
    status:      thread.is_read ? 'replied' : 'waiting',
    leadTag:     tag,
    priority:    tag === 'hot' ? 'high' : tag === 'warm' ? 'medium' : 'low',
    messages,
  };
}
