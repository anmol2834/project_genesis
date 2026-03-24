'use client';

import { useEffect, useState, useRef } from 'react';
import { Box, Typography, useTheme, alpha } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import ReplyRoundedIcon from '@mui/icons-material/ReplyRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import NotificationsRoundedIcon from '@mui/icons-material/NotificationsRounded';

const INITIAL_EVENTS = [
  { id: 1, icon: AutoAwesomeRoundedIcon, color: '#8b5cf6', label: 'AI auto-replied', detail: 'Mike Torres — partnership inquiry', time: 'just now' },
  { id: 2, icon: ReplyRoundedIcon,       color: '#10b981', label: 'Reply received',  detail: 'Sarah Anderson — Q4 proposal',    time: '2m ago' },
  { id: 3, icon: EmailRoundedIcon,       color: '#6366f1', label: 'Email received',  detail: 'Lisa Ventures — follow-up',        time: '5m ago' },
  { id: 4, icon: BoltRoundedIcon,        color: '#f59e0b', label: 'Campaign sent',   detail: 'Q4 Outreach — 48 recipients',      time: '12m ago' },
  { id: 5, icon: ReplyRoundedIcon,       color: '#10b981', label: 'Reply received',  detail: 'James Dev — integration query',    time: '18m ago' },
];

const NEW_EVENTS = [
  { id: 6, icon: EmailRoundedIcon,       color: '#6366f1', label: 'Email received',  detail: 'Priya Rajan — campaign results',   time: 'just now' },
  { id: 7, icon: AutoAwesomeRoundedIcon, color: '#8b5cf6', label: 'AI draft ready',  detail: 'Priya Rajan — reply suggested',    time: 'just now' },
];

export default function ActivityFeed() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [events, setEvents] = useState(INITIAL_EVENTS);
  const newIdx = useRef(0);

  useEffect(() => {
    const interval = setInterval(() => {
      const next = NEW_EVENTS[newIdx.current % NEW_EVENTS.length];
      newIdx.current++;
      setEvents(prev => [{ ...next, id: Date.now(), time: 'just now' }, ...prev.slice(0, 6)]);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Box sx={{
      borderRadius: '14px',
      border: `1px solid ${theme.palette.divider}`,
      background: theme.palette.background.paper,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <Box sx={{
        display: 'flex', alignItems: 'center', gap: 1,
        px: 2, py: 1.5,
        borderBottom: `1px solid ${theme.palette.divider}`,
      }}>
        <NotificationsRoundedIcon sx={{ fontSize: 15, color: 'text.secondary' }} />
        <Typography sx={{ fontSize: '0.82rem', fontWeight: 600, color: 'text.primary' }}>
          Live Activity
        </Typography>
        <Box
          component={motion.div}
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          sx={{ ml: 'auto', width: 6, height: 6, borderRadius: '50%', background: '#10b981' }}
        />
      </Box>

      {/* Timeline */}
      <Box sx={{ px: 2, py: 1.5, display: 'flex', flexDirection: 'column', gap: 0 }}>
        <AnimatePresence initial={false}>
          {events.map((event, i) => {
            const Icon = event.icon;
            return (
              <motion.div
                key={event.id}
                initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                animate={{ opacity: 1, height: 'auto', marginBottom: 0 }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3, ease: 'easeOut' }}
              >
                <Box sx={{ display: 'flex', gap: 1.5, pb: i < events.length - 1 ? 1.25 : 0, position: 'relative' }}>
                  {/* Timeline line */}
                  {i < events.length - 1 && (
                    <Box sx={{
                      position: 'absolute',
                      left: 12, top: 24, bottom: 0,
                      width: 1,
                      background: alpha(theme.palette.divider, 0.8),
                    }} />
                  )}

                  {/* Icon dot */}
                  <Box sx={{
                    width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                    background: alpha(event.color, isDark ? 0.18 : 0.1),
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    zIndex: 1,
                    border: `1.5px solid ${alpha(event.color, isDark ? 0.3 : 0.2)}`,
                  }}>
                    <Icon sx={{ fontSize: 11, color: event.color }} />
                  </Box>

                  {/* Content */}
                  <Box sx={{ flex: 1, minWidth: 0, pt: 0.2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.2 }}>
                      <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: 'text.primary' }}>
                        {event.label}
                      </Typography>
                      <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', flexShrink: 0, ml: 1 }}>
                        {event.time}
                      </Typography>
                    </Box>
                    <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {event.detail}
                    </Typography>
                  </Box>
                </Box>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </Box>
    </Box>
  );
}
