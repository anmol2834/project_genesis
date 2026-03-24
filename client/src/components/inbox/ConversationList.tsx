'use client';

import { useState } from 'react';
import { Box, Typography, useTheme, alpha, InputBase } from '@mui/material';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import LocalFireDepartmentRoundedIcon from '@mui/icons-material/LocalFireDepartmentRounded';
import { CONVERSATIONS, FilterTab, Conversation, LeadTag } from './inboxData';

const FILTERS: { id: FilterTab; label: string }[] = [
  { id: 'all',    label: 'All' },
  { id: 'unread', label: 'Unread' },
  { id: 'hot',    label: 'Hot Leads' },
];

const LEAD_DOT_COLORS: Record<LeadTag, string> = {
  hot:  '#ef4444',
  warm: '#f97316',
  cold: '#60a5fa',
};

const LEAD_TAG_CONFIG: Record<LeadTag, { label: string; color: string; bg: string }> = {
  hot:  { label: 'Hot',  color: '#ef4444', bg: 'rgba(239,68,68,0.12)'  },
  warm: { label: 'Warm', color: '#f97316', bg: 'rgba(249,115,22,0.12)' },
  cold: { label: 'Cold', color: '#60a5fa', bg: 'rgba(96,165,250,0.12)' },
};

interface Props {
  activeId: string;
  onSelect: (c: Conversation) => void;
}

export default function ConversationList({ activeId, onSelect }: Props) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [filter, setFilter] = useState<FilterTab>('all');
  const [search, setSearch] = useState('');

  // CONVERSATIONS is already sorted hot→warm→cold from inboxData
  const filtered = CONVERSATIONS.filter((c) => {
    if (filter === 'unread' && c.unread === 0) return false;
    if (filter === 'hot' && c.leadTag !== 'hot') return false;
    if (search && !c.name.toLowerCase().includes(search.toLowerCase()) &&
        !c.subject.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <Box sx={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: isDark ? 'rgba(15,10,40,0.6)' : theme.palette.background.paper,
      borderRight: `1px solid ${theme.palette.divider}`,
    }}>
      {/* Header */}
      <Box sx={{ px: 2, pt: 2, pb: 1.5, flexShrink: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
          <Typography sx={{ fontSize: '1rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'text.primary' }}>
            Inbox
          </Typography>
          <Box sx={{
            px: 0.75, py: 0.3, borderRadius: '6px',
            background: alpha('#818cf8', isDark ? 0.2 : 0.1),
            border: `1px solid ${alpha('#818cf8', 0.3)}`,
          }}>
            <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: '#818cf8' }}>
              {CONVERSATIONS.reduce((a, c) => a + c.unread, 0)} new
            </Typography>
          </Box>
        </Box>

        {/* Search */}
        <Box sx={{
          display: 'flex', alignItems: 'center', gap: 1,
          px: 1.25, py: 0.75, borderRadius: '10px', mb: 1.5,
          background: isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04),
          border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider}`,
        }}>
          <SearchRoundedIcon sx={{ fontSize: 15, color: 'text.disabled', flexShrink: 0 }} />
          <InputBase
            placeholder="Search conversations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            sx={{ fontSize: '0.78rem', color: 'text.primary', flex: 1,
              '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 } }}
          />
        </Box>

        {/* Filter tabs */}
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          {FILTERS.map((f) => (
            <Box key={f.id} component="button" onClick={() => setFilter(f.id)} sx={{
              px: 1.1, py: 0.4, borderRadius: '7px', border: 'none', cursor: 'pointer',
              fontSize: '0.68rem', fontWeight: filter === f.id ? 700 : 500,
              background: filter === f.id
                ? isDark ? 'rgba(129,140,248,0.2)' : alpha(theme.palette.primary.main, 0.1)
                : 'transparent',
              color: filter === f.id
                ? (isDark ? '#818cf8' : theme.palette.primary.main)
                : theme.palette.text.secondary,
              transition: 'all 0.15s ease',
              '&:hover': { background: isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.05) },
            }}>
              {f.id === 'hot' && (
                <LocalFireDepartmentRoundedIcon sx={{ fontSize: 10, mr: 0.3, verticalAlign: 'middle', color: filter === f.id ? '#ef4444' : 'inherit' }} />
              )}
              {f.label}
            </Box>
          ))}
        </Box>
      </Box>

      {/* List */}
      <Box sx={{ flex: 1, overflowY: 'auto',
        '&::-webkit-scrollbar': { width: 3 },
        '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
      }}>
        {filtered.map((conv) => {
          const isActive = conv.id === activeId;
          const tag = LEAD_TAG_CONFIG[conv.leadTag];
          return (
            <Box key={conv.id} onClick={() => onSelect(conv)} sx={{
              display: 'flex', alignItems: 'flex-start', gap: 1.25,
              px: 1.5, py: 1.25, cursor: 'pointer', position: 'relative',
              background: isActive
                ? isDark ? 'rgba(129,140,248,0.12)' : alpha(theme.palette.primary.main, 0.07)
                : 'transparent',
              borderLeft: isActive
                ? `3px solid ${isDark ? '#818cf8' : theme.palette.primary.main}`
                : '3px solid transparent',
              transition: 'background 0.15s ease',
              '&:hover': {
                background: isActive
                  ? isDark ? 'rgba(129,140,248,0.15)' : alpha(theme.palette.primary.main, 0.09)
                  : isDark ? 'rgba(255,255,255,0.04)' : alpha(theme.palette.text.primary, 0.03),
              },
            }}>
              {/* Avatar */}
              <Box sx={{ position: 'relative', flexShrink: 0 }}>
                <Box sx={{
                  width: 40, height: 40, borderRadius: '50%',
                  background: alpha(conv.avatarColor, isDark ? 0.22 : 0.12),
                  border: `1.5px solid ${alpha(conv.avatarColor, isDark ? 0.4 : 0.25)}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: conv.avatarColor }}>
                    {conv.avatar}
                  </Typography>
                </Box>
                {/* Lead tag dot */}
                <Box sx={{
                  position: 'absolute', bottom: 1, right: 1,
                  width: 8, height: 8, borderRadius: '50%',
                  background: LEAD_DOT_COLORS[conv.leadTag],
                  border: `1.5px solid ${isDark ? '#0f172a' : '#fff'}`,
                  boxShadow: conv.leadTag === 'hot' ? `0 0 5px ${LEAD_DOT_COLORS.hot}` : 'none',
                }} />
              </Box>

              {/* Content */}
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6, minWidth: 0, flex: 1 }}>
                    <Typography sx={{
                      fontSize: '0.8rem', fontWeight: conv.unread > 0 ? 700 : 500,
                      color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {conv.name}
                    </Typography>
                    {/* Lead tag */}
                    <Box sx={{
                      flexShrink: 0, px: 0.55, py: 0.1, borderRadius: '4px',
                      background: tag.bg,
                      border: `1px solid ${alpha(tag.color, 0.25)}`,
                      display: 'flex', alignItems: 'center', gap: 0.25,
                    }}>
                      {conv.leadTag === 'hot' && (
                        <LocalFireDepartmentRoundedIcon sx={{ fontSize: 8, color: tag.color }} />
                      )}
                      <Typography sx={{ fontSize: '0.5rem', fontWeight: 700, color: tag.color, lineHeight: 1 }}>
                        {tag.label}
                      </Typography>
                    </Box>
                  </Box>
                  <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled', flexShrink: 0, ml: 0.5 }}>
                    {conv.time}
                  </Typography>
                </Box>

                <Typography sx={{
                  fontSize: '0.72rem', fontWeight: conv.unread > 0 ? 600 : 400,
                  color: conv.unread > 0 ? 'text.primary' : 'text.secondary',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', mb: 0.3,
                }}>
                  {conv.subject}
                </Typography>

                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Typography sx={{
                    fontSize: '0.67rem', color: 'text.disabled',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
                  }}>
                    {conv.snippet}
                  </Typography>
                  {conv.unread > 0 && (
                    <Box sx={{
                      minWidth: 16, height: 16, borderRadius: '8px', ml: 0.5,
                      background: isDark ? '#818cf8' : theme.palette.primary.main,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', px: 0.4,
                    }}>
                      <Typography sx={{ fontSize: '0.52rem', fontWeight: 800, color: '#fff', lineHeight: 1 }}>
                        {conv.unread}
                      </Typography>
                    </Box>
                  )}
                </Box>
              </Box>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
