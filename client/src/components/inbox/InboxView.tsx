'use client';

import { useState, useMemo, memo } from 'react';
import { Box, Typography, useTheme, alpha } from '@mui/material';
import ConversationList from './ConversationList';
import ChatView from './ChatView';
import { useInboxThreads } from '@/hooks/queries/useInboxThreads';
import { threadToConversation } from './inboxAdapter';
import type { Conversation } from './inboxData';

// ── Loading skeleton ──────────────────────────────────────────────────────────
const LoadingSkeleton = memo(function LoadingSkeleton({ isDark }: { isDark: boolean }) {
  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Box key={i} sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start' }}>
          <Box sx={{
            width: 40, height: 40, borderRadius: '50%', flexShrink: 0,
            background: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(15,23,42,0.06)',
            animation: 'pulse 1.5s ease-in-out infinite',
            '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.4 } },
          }} />
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 0.75 }}>
            <Box sx={{ height: 12, borderRadius: 6, width: '60%', background: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(15,23,42,0.06)', animation: 'pulse 1.5s ease-in-out infinite' }} />
            <Box sx={{ height: 10, borderRadius: 6, width: '85%', background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(15,23,42,0.04)', animation: 'pulse 1.5s ease-in-out infinite' }} />
            <Box sx={{ height: 10, borderRadius: 6, width: '45%', background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(15,23,42,0.03)', animation: 'pulse 1.5s ease-in-out infinite' }} />
          </Box>
        </Box>
      ))}
    </Box>
  );
});

// ── Empty state ───────────────────────────────────────────────────────────────
const EmptyInbox = memo(function EmptyInbox({ isDark }: { isDark: boolean }) {
  return (
    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', p: 4, gap: 1.5 }}>
      <Box sx={{
        width: 56, height: 56, borderRadius: '16px',
        background: isDark ? 'rgba(129,140,248,0.1)' : 'rgba(67,56,202,0.07)',
        border: `1px solid ${isDark ? 'rgba(129,140,248,0.2)' : 'rgba(67,56,202,0.12)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '1.5rem',
      }}>
        📭
      </Box>
      <Typography sx={{ fontSize: '0.85rem', fontWeight: 600, color: 'text.primary' }}>
        No conversations yet
      </Typography>
      <Typography sx={{ fontSize: '0.72rem', color: 'text.disabled', textAlign: 'center', maxWidth: 200 }}>
        Connect an email account to start receiving messages in real-time.
      </Typography>
    </Box>
  );
});

// ── Empty chat placeholder ────────────────────────────────────────────────────
const SelectConversation = memo(function SelectConversation({ isDark }: { isDark: boolean }) {
  return (
    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 1.5 }}>
      <Box sx={{
        width: 64, height: 64, borderRadius: '18px',
        background: isDark ? 'rgba(129,140,248,0.08)' : 'rgba(67,56,202,0.05)',
        border: `1px solid ${isDark ? 'rgba(129,140,248,0.15)' : 'rgba(67,56,202,0.1)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '1.75rem',
      }}>
        💬
      </Box>
      <Typography sx={{ fontSize: '0.85rem', fontWeight: 600, color: 'text.secondary' }}>
        Select a conversation
      </Typography>
    </Box>
  );
});

// ── Main component ────────────────────────────────────────────────────────────
export default function InboxView() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  const {
    data,
    isLoading,
    isError,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
  } = useInboxThreads();

  // Flatten all pages into a single array of Conversation objects
  const conversations = useMemo<Conversation[]>(() => {
    if (!data) return [];
    return data.pages
      .flatMap((page) => page.threads)
      .map(threadToConversation);
  }, [data]);

  const [activeId, setActiveId] = useState<string | null>(null);
  const [mobileShowChat, setMobileShowChat] = useState(false);

  // Active conversation — falls back to first when list loads
  const active = useMemo<Conversation | null>(() => {
    if (conversations.length === 0) return null;
    return conversations.find(c => c.id === activeId) ?? conversations[0];
  }, [conversations, activeId]);

  const handleSelect = (c: Conversation) => {
    setActiveId(c.id);
    setMobileShowChat(true);
  };

  return (
    <Box sx={{
      display: 'flex',
      height: '100%',
      overflow: 'hidden',
      background: isDark ? '#080d18' : theme.palette.background.default,
    }}>
      {/* ── Left: conversation list ── */}
      <Box sx={{
        width: { xs: '100%', sm: 300, md: 320 },
        flexShrink: 0,
        display: {
          xs: mobileShowChat ? 'none' : 'flex',
          sm: 'flex',
        },
        flexDirection: 'column',
        height: '100%',
        borderRight: { sm: `1px solid ${theme.palette.divider}` },
      }}>
        {isLoading ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', background: isDark ? 'rgba(15,10,40,0.6)' : theme.palette.background.paper }}>
            <Box sx={{ px: 2, pt: 2, pb: 1.5 }}>
              <Box sx={{ height: 20, borderRadius: 6, width: '40%', background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)', mb: 1.5, animation: 'pulse 1.5s ease-in-out infinite', '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.4 } } }} />
            </Box>
            <LoadingSkeleton isDark={isDark} />
          </Box>
        ) : isError ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', background: isDark ? 'rgba(15,10,40,0.6)' : theme.palette.background.paper, alignItems: 'center', justifyContent: 'center', p: 3, gap: 1 }}>
            <Typography sx={{ fontSize: '0.8rem', color: 'text.disabled', textAlign: 'center' }}>
              Failed to load inbox. Check your connection.
            </Typography>
          </Box>
        ) : conversations.length === 0 ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', background: isDark ? 'rgba(15,10,40,0.6)' : theme.palette.background.paper }}>
            <Box sx={{ px: 2, pt: 2, pb: 1.5 }}>
              <Typography sx={{ fontSize: '1rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'text.primary' }}>
                Inbox
              </Typography>
            </Box>
            <EmptyInbox isDark={isDark} />
          </Box>
        ) : (
          <ConversationList
            conversations={conversations}
            activeId={active?.id ?? ''}
            onSelect={handleSelect}
            hasNextPage={hasNextPage}
            isFetchingNextPage={isFetchingNextPage}
            fetchNextPage={fetchNextPage}
          />
        )}
      </Box>

      {/* ── Right: chat view ── */}
      <Box sx={{
        flex: 1,
        display: {
          xs: mobileShowChat ? 'flex' : 'none',
          sm: 'flex',
        },
        flexDirection: 'column',
        height: '100%',
        minWidth: 0,
      }}>
        {active ? (
          <ChatView
            conversation={active}
            onBack={() => setMobileShowChat(false)}
          />
        ) : (
          <SelectConversation isDark={isDark} />
        )}
      </Box>
    </Box>
  );
}
