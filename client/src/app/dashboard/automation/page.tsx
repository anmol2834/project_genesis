'use client';

import { useState } from 'react';
import { Box, Typography, useTheme, alpha } from '@mui/material';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import AccountTreeRoundedIcon from '@mui/icons-material/AccountTreeRounded';
import TuneRoundedIcon from '@mui/icons-material/TuneRounded';
import NotificationsActiveRoundedIcon from '@mui/icons-material/NotificationsActiveRounded';
import SmartToyRoundedIcon from '@mui/icons-material/SmartToyRounded';
import FiberManualRecordRoundedIcon from '@mui/icons-material/FiberManualRecordRounded';
import { lightGradients, darkGradients } from '@/theme/palette';

// ── Animated pulsing node ─────────────────────────────────────────────────────
function PulseNode({ color, size = 8, delay = 0 }: { color: string; size?: number; delay?: number }) {
  return (
    <Box sx={{
      width: size, height: size, borderRadius: '50%', background: color, flexShrink: 0,
      boxShadow: `0 0 ${size * 2}px ${alpha(color, 0.7)}`,
      animation: `nodePulse 2.5s ease-in-out ${delay}s infinite`,
      '@keyframes nodePulse': { '0%,100%': { opacity: 1, transform: 'scale(1)' }, '50%': { opacity: 0.5, transform: 'scale(0.85)' } },
    }} />
  );
}

const UPCOMING_FEATURES = [
  { icon: AccountTreeRoundedIcon, color: '#818cf8', label: 'Visual Workflow Builder',   desc: 'Drag-and-drop automation canvas with conditional branching' },
  { icon: BoltRoundedIcon,        color: '#fbbf24', label: 'Event-Driven Triggers',     desc: 'Fire automations on email opens, replies, link clicks, and more' },
  { icon: SmartToyRoundedIcon,    color: '#c084fc', label: 'AI Decision Engine',        desc: 'Let AI decide the next action based on lead intent and context' },
  { icon: TuneRoundedIcon,        color: '#22d3ee', label: 'Conditional Logic',         desc: 'If/else branches, time delays, and multi-step sequences' },
  { icon: NotificationsActiveRoundedIcon, color: '#34d399', label: 'Real-time Alerts',  desc: 'Instant notifications when automation rules fire or fail' },
  { icon: AutoAwesomeRoundedIcon, color: '#f472b6', label: 'AI Reply Automation',       desc: 'Sub-second AI responses to incoming emails with full context' },
];

export default function AutomationPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  return (
    <Box sx={{
      flex: 1, overflowY: 'auto', overflowX: 'hidden', minHeight: 0, width: '100%',
      '&::-webkit-scrollbar': { width: 4 },
      '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.18), borderRadius: 2 },
    }}>
      <Box sx={{ width: '100%', boxSizing: 'border-box', px: { xs: 2, sm: 3 }, py: { xs: 4, sm: 5 }, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, position: 'relative' }}>

        {/* ── Background glow orbs ── */}
        <Box sx={{ position: 'fixed', top: '10%', left: '50%', transform: 'translateX(-50%)', width: 500, height: 500, borderRadius: '50%', background: isDark ? alpha('#818cf8', 0.06) : alpha('#818cf8', 0.04), filter: 'blur(80px)', pointerEvents: 'none', zIndex: 0 }} />
        <Box sx={{ position: 'fixed', bottom: '10%', right: '10%', width: 300, height: 300, borderRadius: '50%', background: isDark ? alpha('#c084fc', 0.05) : alpha('#c084fc', 0.03), filter: 'blur(60px)', pointerEvents: 'none', zIndex: 0 }} />

        {/* ── Hero ── */}
        <Box sx={{ textAlign: 'center', maxWidth: 560, position: 'relative', zIndex: 1, animation: 'fadeUp 0.5s ease-out', '@keyframes fadeUp': { from: { opacity: 0, transform: 'translateY(16px)' }, to: { opacity: 1, transform: 'translateY(0)' } } }}>

          {/* Animated icon */}
          <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2.5 }}>
            <Box sx={{
              width: 72, height: 72, borderRadius: '20px',
              background: grad.primary,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: `0 16px 48px ${alpha('#818cf8', 0.4)}`,
              animation: 'iconFloat 3s ease-in-out infinite',
              '@keyframes iconFloat': { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-6px)' } },
            }}>
              <BoltRoundedIcon sx={{ fontSize: 36, color: '#fff' }} />
            </Box>
          </Box>

          {/* Badge */}
          <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.6, px: 1.25, py: 0.4, borderRadius: '999px', background: isDark ? alpha('#818cf8', 0.12) : alpha('#818cf8', 0.08), border: `1px solid ${alpha('#818cf8', 0.25)}`, mb: 2 }}>
            <PulseNode color="#818cf8" size={6} />
            <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: isDark ? '#a5b4fc' : '#4338ca' }}>In active development</Typography>
          </Box>

          <Typography sx={{ fontSize: { xs: '1.75rem', sm: '2.2rem' }, fontWeight: 900, letterSpacing: '-0.04em', color: 'text.primary', lineHeight: 1.1, mb: 1.25 }}>
            Automation is{' '}
            <Box component="span" sx={{ background: grad.primary, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              coming soon
            </Box>
          </Typography>

          <Typography sx={{ fontSize: { xs: '0.82rem', sm: '0.9rem' }, color: 'text.secondary', lineHeight: 1.7, mb: 0 }}>
            We're building a powerful visual workflow engine with AI-driven triggers, conditional logic, and real-time event processing — all connected to your email accounts and campaigns.
          </Typography>
        </Box>

        {/* ── Upcoming features grid ── */}
        <Box sx={{ width: '100%', maxWidth: 680, position: 'relative', zIndex: 1, animation: 'fadeUp 0.5s ease-out 0.3s both' }}>
          <Typography sx={{ fontSize: '0.6rem', fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'text.disabled', textAlign: 'center', mb: 2 }}>
            What's being built
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 1 }}>
            {UPCOMING_FEATURES.map((f, i) => {
              const Icon = f.icon;
              return (
                <Box key={f.label} sx={{
                  display: 'flex', alignItems: 'flex-start', gap: 1.25, px: 1.5, py: 1.25, borderRadius: '13px',
                  background: isDark ? alpha(f.color, 0.06) : alpha(f.color, 0.04),
                  border: `1px solid ${alpha(f.color, isDark ? 0.15 : 0.1)}`,
                  transition: 'all 0.18s',
                  animation: `fadeUp 0.4s ease-out ${0.35 + i * 0.06}s both`,
                  '&:hover': { background: isDark ? alpha(f.color, 0.12) : alpha(f.color, 0.08), borderColor: alpha(f.color, isDark ? 0.3 : 0.2), transform: 'translateY(-2px)' },
                }}>
                  <Box sx={{ width: 32, height: 32, borderRadius: '9px', flexShrink: 0, background: alpha(f.color, isDark ? 0.18 : 0.12), display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Icon sx={{ fontSize: 16, color: f.color }} />
                  </Box>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: 'text.primary', mb: 0.2 }}>{f.label}</Typography>
                    <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', lineHeight: 1.5 }}>{f.desc}</Typography>
                  </Box>
                </Box>
              );
            })}
          </Box>
        </Box>

        {/* ── Progress indicator ── */}
        <Box sx={{ width: '100%', maxWidth: 420, position: 'relative', zIndex: 1, animation: 'fadeUp 0.5s ease-out 0.7s both' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.75 }}>
            <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: 'text.secondary' }}>Development progress</Typography>
            <Typography sx={{ fontSize: '0.65rem', fontWeight: 800, color: '#818cf8' }}>68%</Typography>
          </Box>
          <Box sx={{ height: 6, borderRadius: 3, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.07)', overflow: 'hidden' }}>
            <Box sx={{ height: '100%', borderRadius: 3, width: '68%', background: grad.primary, boxShadow: `0 0 10px ${alpha('#818cf8', 0.5)}`, animation: 'progressIn 1.2s ease-out 0.8s both', '@keyframes progressIn': { from: { width: '0%' }, to: { width: '68%' } } }} />
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
            {[
              { label: 'Backend API',     done: true  },
              { label: 'Trigger Engine',  done: true  },
              { label: 'Visual Builder',  done: false },
              { label: 'AI Integration',  done: false },
            ].map(step => (
              <Box key={step.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                <FiberManualRecordRoundedIcon sx={{ fontSize: 7, color: step.done ? '#34d399' : 'text.disabled' }} />
                <Typography sx={{ fontSize: '0.58rem', color: step.done ? '#34d399' : 'text.disabled', fontWeight: step.done ? 600 : 400 }}>{step.label}</Typography>
              </Box>
            ))}
          </Box>
        </Box>

      </Box>
    </Box>
  );
}
