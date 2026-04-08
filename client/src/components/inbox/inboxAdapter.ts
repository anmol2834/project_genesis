/**
 * inboxAdapter.ts
 * Maps InboxThread (emailservice shape) → Conversation (UI shape).
 *
 * Key fixes:
 * - Uses thread.from_email (always populated by backend) — no more "Unknown"
 * - Cleans email content: strips quoted reply chains and normalizes whitespace
 * - Handles both 'incoming' and 'outgoing' direction strings
 */

import type { InboxThread, InboxMessage } from '@/services/endpoints/emailInbox';
import type { Conversation, Message, LeadTag } from './inboxData';

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Derive a human-readable display name from an email address.
 * "john.doe@example.com" → "John Doe"
 * "blackmistfile@gmail.com" → "Blackmistfile"
 */
function nameFromEmail(email: string): string {
  if (!email || email === 'unknown@email.com') return 'Unknown';
  const local = email.split('@')[0] ?? email;
  return local
    .replace(/[._+-]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim() || email;
}

/** Two-letter initials from a display name */
function initials(name: string): string {
  if (!name || name === 'Unknown') return 'UN';
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
function toRole(direction: string): 'received' | 'sent' {
  return direction === 'outgoing' ? 'sent' : 'received';
}

/**
 * Strip all invisible/zero-width Unicode characters from a string.
 * Email clients (Gmail, Outlook) insert these before attribution lines,
 * which breaks simple regex matching on line starts.
 *
 * Covers: ZWSP, ZWNJ, ZWJ, WJ, BOM, soft-hyphen, directional marks,
 * variation selectors, and other format/control characters.
 */
function stripInvisible(s: string): string {
  // eslint-disable-next-line no-control-regex
  return s.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F\u00AD\u200B-\u200F\u2028\u2029\u202A-\u202F\u2060-\u206F\uFEFF\uFFF0-\uFFFF]/g, '');
}

/**
 * Clean email content for display in chat bubbles.
 * - Strips invisible/zero-width Unicode chars (the hidden ¶ before "On ... wrote:")
 * - Strips quoted reply chains (lines starting with ">")
 * - Removes "On ... wrote:" attribution lines (handles multi-line wrapping)
 * - Removes Outlook-style "From: ... Sent: ... To: ..." headers
 * - Normalizes \r\n to \n
 * - Trims excessive blank lines
 */
function cleanContent(raw: string | null): string {
  if (!raw) return '';

  // 1. Normalize line endings and strip invisible chars per-character
  let text = raw
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n');

  // 2. Strip invisible chars from the whole string first (catches mid-line injections)
  text = stripInvisible(text);

  // 3. Handle inline case: HTML-derived content is often a single line where
  //    "On Tue, ..." appears mid-string after a space. Cut there immediately.
  const inlineMatch = text.match(/\s+On\s+(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s/i);
  if (inlineMatch && inlineMatch.index !== undefined) {
    return text.slice(0, inlineMatch.index).trim();
  }

  // 4. Collapse multi-line "On ... wrote:" attribution into a single line
  //    Gmail wraps: "On Tue, 7 Apr 2026 at 7:44 PM John\n<john@example.com> wrote:"
  //    Also handles: "On Tue, Apr 7, 2026 at 10:03PM Name\nwrote:"
  text = text.replace(/\nOn (.+?)\n(<[^>]+>)\s*wrote:/gis, '\nOn $1 $2 wrote:');
  text = text.replace(/\nOn (.+?)\n(wrote:)/gis, '\nOn $1 $2');

  // 5. Walk lines and cut at the first reply-chain marker
  const lines = text.split('\n');
  const cleaned: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();

    // "On <date> <name/email> wrote:" — Gmail/Outlook attribution line
    if (/^On\s.+wrote:\s*$/i.test(trimmed)) break;
    // "On Tue/Mon/..." — start of attribution even without "wrote:"
    if (/^On\s+(Mon|Tue|Wed|Thu|Fri|Sat|Sun|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/i.test(trimmed)) break;

    // Outlook block-quote header: "From: X\nSent: Y\nTo: Z"
    if (/^From:\s*.+/i.test(trimmed) && cleaned.length > 0) break;

    // Quoted lines starting with ">"
    if (trimmed.startsWith('>')) continue;

    // Horizontal separator lines (--- or ___)
    if (/^[-_]{3,}$/.test(trimmed)) break;

    cleaned.push(line);
  }

  return cleaned
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/** Assign a lead tag based on unread count / recency */
function inferLeadTag(thread: InboxThread): LeadTag {
  // Use backend lead_status if available
  if (thread.lead_status === 'hot')  return 'hot';
  if (thread.lead_status === 'warm') return 'warm';
  if (thread.lead_status === 'cold') return 'cold';

  // Fallback: heuristic based on unread + recency
  if (thread.unread > 0) return 'hot';
  const lastAt = thread.last_message_at ? new Date(thread.last_message_at).getTime() : 0;
  const hoursAgo = (Date.now() - lastAt) / 3_600_000;
  if (hoursAgo < 6)  return 'warm';
  return 'cold';
}

// ── Main adapter ──────────────────────────────────────────────────────────────

export function threadToConversation(thread: InboxThread): Conversation {
  /**
   * from_email is always populated by the backend _fmt_conv() function.
   * It contains the "other party" email:
   *   - For incoming threads: the sender's email
   *   - For outgoing threads: the first recipient
   * This eliminates the "Unknown" display name issue.
   */
  const senderEmail = thread.from_email || '';
  const displayName = senderEmail ? nameFromEmail(senderEmail) : 'Unknown';
  const tag         = inferLeadTag(thread);

  // Sort messages by timestamp ASC (oldest first — chat order)
  const sorted = [...(thread.messages ?? [])].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  const messages: Message[] = sorted.map((m: InboxMessage, idx) => ({
    id:            `${thread.thread_id}-${idx}`,
    role:          toRole(m.direction),
    text:          cleanContent(m.content),
    time:          formatTime(m.timestamp),
    status:        m.direction === 'outgoing' ? 'read' : undefined,
    // Pass through draft fields for the ChatView draft banner
    draft_message: m.draft_message ?? undefined,
    message_id:    m.message_id,
    message_state: m.message_state ?? undefined,
  })).filter(m => m.text.length > 0 || m.draft_message);  // keep messages with drafts even if content empty

  // Find the latest pending draft across all messages in this thread
  const draftMsg = sorted.find(m => m.draft_message && m.message_state === 'drafted');

  const latestMsg = sorted[sorted.length - 1];
  const snippet   = thread.snippet
    ? cleanContent(thread.snippet).slice(0, 80)
    : cleanContent(latestMsg?.content)?.slice(0, 80) || '';

  return {
    id:          thread.thread_id,
    name:        displayName,
    email:       senderEmail,
    avatar:      initials(displayName),
    avatarColor: avatarColor(senderEmail || thread.thread_id),
    subject:     thread.subject || '(No Subject)',
    snippet,
    time:        relativeTime(thread.last_message_at),
    unread:      thread.unread ?? 0,
    status:      thread.is_read ? 'replied' : 'waiting',
    leadTag:     tag,
    priority:    tag === 'hot' ? 'high' : tag === 'warm' ? 'medium' : 'low',
    messages,
    // Expose draft for the ChatView draft banner
    draft:          draftMsg?.draft_message ?? undefined,
    draftMessageId: draftMsg?.message_id ?? undefined,
  };
}
