'use client';

import { useState } from 'react';
import { Box, useTheme } from '@mui/material';
import ConversationList from './ConversationList';
import ChatView from './ChatView';
import { CONVERSATIONS, Conversation } from './inboxData';

export default function InboxView() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [active, setActive] = useState<Conversation>(CONVERSATIONS[0]);
  const [mobileShowChat, setMobileShowChat] = useState(false);

  const handleSelect = (c: Conversation) => {
    setActive(c);
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
      {/* Desktop: always visible. Mobile: hidden when chat is open */}
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
        <ConversationList activeId={active.id} onSelect={handleSelect} />
      </Box>

      {/* ── Right: chat view ── */}
      {/* Desktop: always visible. Mobile: only when a chat is selected */}
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
        <ChatView
          conversation={active}
          onBack={() => setMobileShowChat(false)}
        />
      </Box>
    </Box>
  );
}
