'use client';

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  IconButton,
  Button,
  useTheme,
  Stack,
  Divider,
} from '@mui/material';
import NotificationsRoundedIcon from '@mui/icons-material/NotificationsRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import MarkEmailReadRoundedIcon from '@mui/icons-material/MarkEmailReadRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';

interface NotificationItem {
  id: string;
  title: string;
  message: string;
  time: string;
  type: 'automation' | 'email' | 'system';
  read: boolean;
}

const INITIAL_NOTIFICATIONS: NotificationItem[] = [
  {
    id: '1',
    title: 'Customer Email Responded',
    message: 'Automated verified response was dispatched immediately to customer without drafting.',
    time: '2 minutes ago',
    type: 'automation',
    read: false,
  },
  {
    id: '2',
    title: 'Live Email Sync Active',
    message: 'Gmail real-time push webhook received and processed successfully via Cloudflare tunnel.',
    time: '15 minutes ago',
    type: 'email',
    read: false,
  },
  {
    id: '3',
    title: 'Zero-Draft Mode Enabled',
    message: 'Outbound pipeline configured for immediate dispatch via verified business account.',
    time: '1 hour ago',
    type: 'system',
    read: true,
  },
];

export default function NotificationsPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [notifications, setNotifications] = useState<NotificationItem[]>(INITIAL_NOTIFICATIONS);

  const markAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const clearAll = () => {
    setNotifications([]);
  };

  const getIcon = (type: string) => {
    switch (type) {
      case 'automation':
        return <AutoAwesomeRoundedIcon sx={{ color: '#38bdf8', fontSize: 20 }} />;
      case 'email':
        return <SendRoundedIcon sx={{ color: '#34d399', fontSize: 20 }} />;
      default:
        return <NotificationsRoundedIcon sx={{ color: '#a78bfa', fontSize: 20 }} />;
    }
  };

  return (
    <Box sx={{ p: { xs: 2, md: 4 }, maxWidth: 900, mx: 'auto', width: '100%' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box>
          <Typography variant="h5" fontWeight={700} sx={{ color: 'text.primary', display: 'flex', alignItems: 'center', gap: 1 }}>
            <NotificationsRoundedIcon sx={{ color: theme.palette.primary.main }} /> Notifications
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
            Real-time activity, email dispatches, and automation status
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button
            size="small"
            startIcon={<MarkEmailReadRoundedIcon />}
            onClick={markAllRead}
            sx={{ textTransform: 'none', borderRadius: '8px' }}
          >
            Mark all read
          </Button>
          <Button
            size="small"
            color="inherit"
            startIcon={<DeleteOutlineRoundedIcon />}
            onClick={clearAll}
            sx={{ textTransform: 'none', borderRadius: '8px', color: 'text.secondary' }}
          >
            Clear
          </Button>
        </Stack>
      </Box>

      {notifications.length === 0 ? (
        <Paper
          elevation={0}
          sx={{
            p: 6,
            textAlign: 'center',
            borderRadius: '12px',
            border: `1px solid ${theme.palette.divider}`,
            bgcolor: isDark ? 'rgba(15,23,42,0.6)' : 'background.paper',
          }}
        >
          <CheckCircleRoundedIcon sx={{ fontSize: 48, color: '#34d399', mb: 1 }} />
          <Typography variant="h6" fontWeight={600} sx={{ color: 'text.primary' }}>
            You're all caught up!
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
            No new notifications at this time.
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={1.5}>
          {notifications.map((item) => (
            <Paper
              key={item.id}
              elevation={0}
              sx={{
                p: 2,
                borderRadius: '10px',
                border: `1px solid ${theme.palette.divider}`,
                bgcolor: item.read
                  ? isDark
                    ? 'rgba(15,23,42,0.4)'
                    : 'background.paper'
                  : isDark
                  ? 'rgba(30,41,59,0.7)'
                  : '#f8fafc',
                display: 'flex',
                alignItems: 'flex-start',
                gap: 2,
                transition: 'border-color 0.2s ease',
                '&:hover': {
                  borderColor: theme.palette.primary.main,
                },
              }}
            >
              <Box sx={{ mt: 0.5 }}>{getIcon(item.type)}</Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  <Typography variant="subtitle2" fontWeight={700} sx={{ color: 'text.primary' }}>
                    {item.title}
                  </Typography>
                  {!item.read && (
                    <Chip label="New" size="small" sx={{ height: 18, fontSize: '0.65rem', bgcolor: '#f87171', color: '#fff' }} />
                  )}
                  <Typography variant="caption" sx={{ color: 'text.secondary', ml: 'auto' }}>
                    {item.time}
                  </Typography>
                </Box>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  {item.message}
                </Typography>
              </Box>
            </Paper>
          ))}
        </Stack>
      )}
    </Box>
  );
}
