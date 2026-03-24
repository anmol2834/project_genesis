'use client';

import { useState } from 'react';
import { Box, Typography, useTheme, alpha } from '@mui/material';
import RocketLaunchRoundedIcon from '@mui/icons-material/RocketLaunchRounded';
import InboxRoundedIcon from '@mui/icons-material/InboxRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import BarChartRoundedIcon from '@mui/icons-material/BarChartRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import ManageSearchRoundedIcon from '@mui/icons-material/ManageSearchRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import ExtensionRoundedIcon from '@mui/icons-material/ExtensionRounded';
import StorageRoundedIcon from '@mui/icons-material/StorageRounded';

// Regular actions
const ACTIONS = [
  {
    icon: RocketLaunchRoundedIcon,
    label: 'New Campaign',
    color: '#818cf8',
    glow: 'rgba(99,102,241,0.4)',
    bg: 'rgba(99,102,241,0.14)',
    border: 'rgba(129,140,248,0.3)',
    badge: null,
  },
  {
    icon: InboxRoundedIcon,
    label: 'View Inbox',
    color: '#34d399',
    glow: 'rgba(16,185,129,0.4)',
    bg: 'rgba(16,185,129,0.14)',
    border: 'rgba(52,211,153,0.3)',
    badge: '12',
  },
  {
    icon: AutoAwesomeRoundedIcon,
    label: 'Automation',
    color: '#c084fc',
    glow: 'rgba(139,92,246,0.4)',
    bg: 'rgba(139,92,246,0.14)',
    border: 'rgba(192,132,252,0.3)',
    badge: null,
  },
  {
    icon: PeopleRoundedIcon,
    label: 'Leads',
    color: '#4ade80',
    glow: 'rgba(74,222,128,0.4)',
    bg: 'rgba(74,222,128,0.14)',
    border: 'rgba(74,222,128,0.3)',
    badge: null,
  },
  {
    icon: ManageSearchRoundedIcon,
    label: 'Research',
    color: '#22d3ee',
    glow: 'rgba(6,182,212,0.4)',
    bg: 'rgba(6,182,212,0.14)',
    border: 'rgba(34,211,238,0.3)',
    badge: null,
  },
  {
    icon: StorageRoundedIcon,
    label: 'My Data',
    color: '#a78bfa',
    glow: 'rgba(167,139,250,0.4)',
    bg: 'rgba(167,139,250,0.14)',
    border: 'rgba(167,139,250,0.3)',
    badge: null,
  },
  {
    icon: EmailRoundedIcon,
    label: 'Add Account',
    color: '#fb923c',
    glow: 'rgba(249,115,22,0.4)',
    bg: 'rgba(249,115,22,0.14)',
    border: 'rgba(251,146,60,0.3)',
    badge: null,
  },
  {
    icon: BarChartRoundedIcon,
    label: 'Analytics',
    color: '#38bdf8',
    glow: 'rgba(56,189,248,0.4)',
    bg: 'rgba(56,189,248,0.14)',
    border: 'rgba(56,189,248,0.3)',
    badge: null,
  },
  {
    icon: GroupsRoundedIcon,
    label: 'Team',
    color: '#f472b6',
    glow: 'rgba(236,72,153,0.4)',
    bg: 'rgba(236,72,153,0.14)',
    border: 'rgba(244,114,182,0.3)',
    badge: null,
  },
  {
    icon: ExtensionRoundedIcon,
    label: 'Integrations',
    color: '#fbbf24',
    glow: 'rgba(245,158,11,0.4)',
    bg: 'rgba(245,158,11,0.14)',
    border: 'rgba(251,191,36,0.3)',
    badge: null,
  },
];

// Auto-Reply toggle colors
const AUTO_OFF = {
  color: '#64748b',
  bg: 'rgba(100,116,139,0.1)',
  border: 'rgba(100,116,139,0.22)',
  glow: 'rgba(100,116,139,0.3)',
};
const AUTO_ON = {
  color: '#fbbf24',
  bg: 'rgba(245,158,11,0.18)',
  border: 'rgba(251,191,36,0.4)',
  glow: 'rgba(245,158,11,0.45)',
};

export default function QuickActions() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [autoReply, setAutoReply] = useState(false);

  const ar = autoReply ? AUTO_ON : AUTO_OFF;

  return (
    <Box
      sx={{
        borderRadius: '16px',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
        background: isDark ? 'rgba(15,23,42,0.6)' : theme.palette.background.paper,
        backdropFilter: isDark ? 'blur(12px)' : 'none',
        px: { xs: 2, sm: 3 },
        py: { xs: 2, sm: 2.5 },
      }}
    >
      <Typography
        sx={{
          fontSize: { xs: '0.95rem', sm: '1rem' },
          fontWeight: 700,
          color: 'text.primary',
          letterSpacing: '-0.02em',
          mb: { xs: 2, sm: 2.5 },
        }}
      >
        What would you like to do?
      </Typography>

      <Box
        sx={{
          display: 'flex',
          gap: { xs: 2, sm: 2.5 },
          overflowX: 'auto',
          overflowY: 'visible',
          pt: 1,
          pb: 1,
          mx: -0.5,
          px: 0.5,
          '&::-webkit-scrollbar': { height: 3 },
          '&::-webkit-scrollbar-track': { background: 'transparent' },
          '&::-webkit-scrollbar-thumb': {
            background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
            borderRadius: 2,
          },
        }}
      >
        {/* ── Auto-Reply toggle (first slot) ── */}
        <Box
          component="button"
          onClick={() => setAutoReply(v => !v)}
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 0.75,
            flexShrink: 0,
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            outline: 'none',
            p: 0,
            '&:hover .qa-circle': {
              transform: 'translateY(-4px) scale(1.06)',
              boxShadow: `0 10px 28px ${alpha(ar.color, isDark ? 0.45 : 0.3)}`,
            },
            '&:active .qa-circle': { transform: 'translateY(-1px) scale(1.02)' },
          }}
        >
          <Box
            className="qa-circle"
            sx={{
              width: { xs: 46, sm: 50 },
              height: { xs: 46, sm: 50 },
              borderRadius: '50%',
              background: isDark ? ar.bg : alpha(ar.color, autoReply ? 0.14 : 0.08),
              border: `1.5px solid ${isDark ? ar.border : alpha(ar.color, autoReply ? 0.3 : 0.18)}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              transition: 'all 0.25s ease',
              boxShadow: autoReply
                ? `0 0 0 3px ${alpha(AUTO_ON.color, isDark ? 0.22 : 0.15)}`
                : 'none',
            }}
          >
            <BoltRoundedIcon sx={{ fontSize: { xs: 19, sm: 21 }, color: ar.color, transition: 'color 0.25s ease' }} />

            {/* ON/OFF pill */}
            <Box sx={{
              position: 'absolute',
              bottom: -4,
              left: '50%',
              transform: 'translateX(-50%)',
              px: 0.6,
              height: 13,
              borderRadius: '6px',
              background: autoReply ? AUTO_ON.color : (isDark ? 'rgba(100,116,139,0.5)' : 'rgba(148,163,184,0.4)'),
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: `1.5px solid ${isDark ? '#0f172a' : '#fff'}`,
              transition: 'background 0.25s ease',
            }}>
              <Typography sx={{ fontSize: '0.42rem', fontWeight: 800, color: '#fff', lineHeight: 1, letterSpacing: '0.04em' }}>
                {autoReply ? 'ON' : 'OFF'}
              </Typography>
            </Box>
          </Box>

          <Typography
            sx={{
              fontSize: { xs: '0.62rem', sm: '0.65rem' },
              fontWeight: autoReply ? 700 : 500,
              color: autoReply
                ? AUTO_ON.color
                : (isDark ? 'rgba(255,255,255,0.45)' : theme.palette.text.disabled),
              whiteSpace: 'nowrap',
              transition: 'color 0.25s ease',
            }}
          >
            Auto-Reply
          </Typography>
        </Box>

        {/* ── Regular action buttons ── */}
        {ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <Box
              key={action.label}
              component="button"
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 0.75,
                flexShrink: 0,
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                outline: 'none',
                p: 0,
                '&:hover .qa-circle': {
                  transform: 'translateY(-4px) scale(1.06)',
                  boxShadow: `0 10px 28px ${alpha(action.color, isDark ? 0.45 : 0.3)}`,
                  borderColor: alpha(action.color, 0.6),
                  background: isDark ? alpha(action.color, 0.28) : alpha(action.color, 0.18),
                },
                '&:active .qa-circle': { transform: 'translateY(-1px) scale(1.02)' },
              }}
            >
              <Box
                className="qa-circle"
                sx={{
                  width: { xs: 46, sm: 50 },
                  height: { xs: 46, sm: 50 },
                  borderRadius: '50%',
                  background: isDark ? action.bg : alpha(action.color, 0.1),
                  border: `1.5px solid ${isDark ? action.border : alpha(action.color, 0.22)}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  position: 'relative',
                  transition: 'transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease, border-color 0.2s ease',
                }}
              >
                <Icon sx={{ fontSize: { xs: 19, sm: 21 }, color: action.color }} />
                {action.badge && (
                  <Box sx={{
                    position: 'absolute', top: 2, right: 2,
                    minWidth: 18, height: 18, borderRadius: '9px',
                    background: action.color,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    px: 0.5,
                    border: `2px solid ${isDark ? '#0f172a' : '#fff'}`,
                  }}>
                    <Typography sx={{ fontSize: '0.52rem', fontWeight: 800, color: '#fff', lineHeight: 1 }}>
                      {action.badge}
                    </Typography>
                  </Box>
                )}
              </Box>

              <Typography
                sx={{
                  fontSize: { xs: '0.62rem', sm: '0.65rem' },
                  fontWeight: 500,
                  color: isDark ? 'rgba(255,255,255,0.55)' : theme.palette.text.secondary,
                  whiteSpace: 'nowrap',
                  letterSpacing: '-0.005em',
                }}
              >
                {action.label}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
