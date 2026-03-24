'use client';

import { Box, Typography, useTheme, alpha } from '@mui/material';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import InboxRoundedIcon from '@mui/icons-material/InboxRounded';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';

const THREADS = [
  { avatar: 'SA', color: '#818cf8', name: 'Sarah Anderson', subject: 'Q4 proposal review — need your input',   snippet: 'Hi, I wanted to follow up on the proposal we discussed last week...', time: '2m ago',  unread: true,  aiHandled: false },
  { avatar: 'MT', color: '#c084fc', name: 'Mike Torres',    subject: 'Partnership opportunity with TechCorp',  snippet: 'We have an exciting opportunity that aligns perfectly with your goals...', time: '14m ago', unread: true,  aiHandled: true },
  { avatar: 'LV', color: '#22d3ee', name: 'Lisa Ventures',  subject: 'Follow-up on our call yesterday',        snippet: 'Great speaking with you! As discussed, I am attaching the deck...', time: '1h ago',  unread: false, aiHandled: true },
  { avatar: 'JD', color: '#34d399', name: 'James Dev',      subject: 'Integration question — urgent',          snippet: 'Quick question about the API integration we are working on...', time: '2h ago',  unread: false, aiHandled: false },
  { avatar: 'PR', color: '#fbbf24', name: 'Priya Rajan',    subject: 'Campaign results — Q3 summary',          snippet: 'Sharing the final numbers from our Q3 outreach campaign...', time: '3h ago',  unread: false, aiHandled: true },
];

export default function InboxPreview() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  return (
    <Box sx={{
      borderRadius: '14px',
      border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
      background: isDark ? 'rgba(30,27,75,0.5)' : theme.palette.background.paper,
      overflow: 'hidden',
      backdropFilter: isDark ? 'blur(12px)' : 'none',
    }}>
      {/* Header */}
      <Box sx={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        px: 2, py: 1.5,
        borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
        background: isDark ? 'rgba(129,140,248,0.06)' : alpha(theme.palette.primary.main, 0.03),
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <InboxRoundedIcon sx={{ fontSize: 15, color: isDark ? '#818cf8' : 'primary.main' }} />
          <Typography sx={{ fontSize: '0.82rem', fontWeight: 600, color: 'text.primary' }}>
            Recent Conversations
          </Typography>
          <Box sx={{
            minWidth: 18, height: 18, borderRadius: '9px',
            background: isDark ? '#818cf8' : theme.palette.primary.main,
            display: 'flex', alignItems: 'center', justifyContent: 'center', px: 0.5,
          }}>
            <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: '#fff' }}>12</Typography>
          </Box>
        </Box>
        <Box sx={{
          display: 'flex', alignItems: 'center', gap: 0.4,
          cursor: 'pointer',
          color: isDark ? '#818cf8' : 'primary.main',
          '&:hover': { opacity: 0.75 },
          transition: 'opacity 0.15s',
        }}>
          <Typography sx={{ fontSize: '0.7rem', fontWeight: 600 }}>View all</Typography>
          <ArrowForwardRoundedIcon sx={{ fontSize: 12 }} />
        </Box>
      </Box>

      {/* Thread list */}
      <Box>
        {THREADS.map((thread, i) => (
          <Box
            key={thread.name}
            sx={{
              display: 'flex', alignItems: 'flex-start', gap: 1.5,
              px: 2, py: 1.4,
              borderBottom: i < THREADS.length - 1
                ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.divider, 0.7)}`
                : 'none',
              cursor: 'pointer',
              transition: 'background 0.15s ease',
              '&:hover': {
                background: isDark ? 'rgba(129,140,248,0.06)' : theme.palette.action.hover,
              },
            }}
          >
            {/* Avatar */}
            <Box sx={{
              width: 34, height: 34, borderRadius: '50%', flexShrink: 0,
              background: alpha(thread.color, isDark ? 0.2 : 0.12),
              border: `1.5px solid ${alpha(thread.color, isDark ? 0.35 : 0.2)}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              position: 'relative',
            }}>
              <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: thread.color }}>
                {thread.avatar}
              </Typography>
              {thread.unread && (
                <Box sx={{
                  position: 'absolute', top: -1, right: -1,
                  width: 8, height: 8, borderRadius: '50%',
                  background: '#818cf8',
                  border: `1.5px solid ${isDark ? '#0f172a' : '#fff'}`,
                }} />
              )}
            </Box>

            {/* Content */}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.25 }}>
                <Typography sx={{
                  fontSize: '0.78rem', fontWeight: thread.unread ? 700 : 500,
                  color: thread.unread
                    ? (isDark ? '#fff' : 'text.primary')
                    : 'text.primary',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  maxWidth: '58%',
                }}>
                  {thread.name}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6, flexShrink: 0 }}>
                  {thread.aiHandled && (
                    <Box sx={{
                      display: 'flex', alignItems: 'center', gap: 0.3,
                      px: 0.5, py: 0.15, borderRadius: '4px',
                      background: alpha('#c084fc', isDark ? 0.18 : 0.1),
                    }}>
                      <AutoAwesomeRoundedIcon sx={{ fontSize: 9, color: '#c084fc' }} />
                      <Typography sx={{ fontSize: '0.55rem', fontWeight: 600, color: '#c084fc' }}>AI</Typography>
                    </Box>
                  )}
                  <Typography sx={{ fontSize: '0.63rem', color: 'text.disabled' }}>
                    {thread.time}
                  </Typography>
                </Box>
              </Box>
              <Typography sx={{
                fontSize: '0.72rem',
                fontWeight: thread.unread ? 600 : 400,
                color: thread.unread
                  ? (isDark ? 'rgba(255,255,255,0.8)' : 'text.primary')
                  : 'text.secondary',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                mb: 0.2,
              }}>
                {thread.subject}
              </Typography>
              <Typography sx={{
                fontSize: '0.67rem', color: 'text.disabled',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {thread.snippet}
              </Typography>
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
