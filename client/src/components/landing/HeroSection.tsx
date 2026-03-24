'use client';

import { useEffect, useState } from 'react';
import { Box, Button, Chip, Typography, useTheme, alpha, useMediaQuery } from '@mui/material';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import { motion, AnimatePresence } from 'framer-motion';
import { lightGradients, darkGradients } from '@/theme/palette';

const EMAILS = [
  { from: 'sarah@acme.com',    subject: 'Partnership proposal for Q4',    time: '2s ago',  avatar: 'S', color: '#6366f1' },
  { from: 'john@techcorp.io',  subject: 'Following up on our demo call',  time: '18s ago', avatar: 'J', color: '#8b5cf6' },
  { from: 'lisa@startup.co',   subject: 'Can we schedule a quick call?',  time: '1m ago',  avatar: 'L', color: '#06b6d4' },
];

const AI_REPLIES = [
  "Thank you for reaching out! I'd love to explore this partnership. Let's schedule a call this week.",
  "Hi John, great connecting with you! I'll send over the details by EOD today.",
  "Hi Lisa, absolutely! I'm available Thursday 2-4 PM or Friday morning. Which works best?",
];

function delay(ms: number) { return new Promise((r) => setTimeout(r, ms)); }

function LiveInboxDemo() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const [activeIdx, setActiveIdx] = useState(0);
  const [showReply, setShowReply] = useState(false);
  const [typedText, setTypedText] = useState('');
  const [phase, setPhase] = useState<'email' | 'thinking' | 'reply'>('email');

  useEffect(() => {
    let cancelled = false;
    const cycle = async () => {
      if (cancelled) return;
      setPhase('email'); setShowReply(false); setTypedText('');
      await delay(1200); if (cancelled) return;
      setPhase('thinking');
      await delay(900); if (cancelled) return;
      setPhase('reply'); setShowReply(true);
      const target = AI_REPLIES[activeIdx];
      // Faster typing on mobile to reduce animation load
      const charDelay = isMobile ? 22 : 18;
      for (let i = 0; i <= target.length; i++) {
        if (cancelled) return;
        setTypedText(target.slice(0, i));
        await delay(charDelay);
      }
      await delay(2200); if (cancelled) return;
      setActiveIdx((p) => (p + 1) % EMAILS.length);
    };
    cycle();
    return () => { cancelled = true; };
  }, [activeIdx, isMobile]); // eslint-disable-line

  return (
    <Box
      sx={{
        borderRadius: { xs: '16px', sm: '20px' },
        border: `1px solid ${theme.palette.divider}`,
        background: theme.palette.background.paper,
        overflow: 'hidden',
        boxShadow: isDark
          ? '0 24px 48px rgba(0,0,0,0.45), 0 0 0 1px rgba(129,140,248,0.12)'
          : '0 24px 48px rgba(15,23,42,0.09), 0 0 0 1px rgba(67,56,202,0.07)',
        width: '100%',
        // Never overflow the viewport on any phone
        maxWidth: { xs: '100%', sm: 480 },
      }}
    >
      {/* Window chrome */}
      <Box sx={{ px: { xs: 1.5, sm: 2 }, py: 1.5, borderBottom: `1px solid ${theme.palette.divider}`, display: 'flex', alignItems: 'center', gap: 0.75 }}>
        {['#ff5f57', '#febc2e', '#28c840'].map((c) => (
          <Box key={c} sx={{ width: { xs: 8, sm: 10 }, height: { xs: 8, sm: 10 }, borderRadius: '50%', background: c, flexShrink: 0 }} />
        ))}
        <Box sx={{ flex: 1, mx: { xs: 1, sm: 2 }, height: 20, borderRadius: '6px', background: alpha(theme.palette.text.primary, 0.05), display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Typography sx={{ color: 'text.disabled', fontSize: '0.65rem' }}>inbox.mailflow.ai</Typography>
        </Box>
      </Box>

      {/* Inbox list */}
      <Box sx={{ p: { xs: 1, sm: 1.5 }, borderBottom: `1px solid ${theme.palette.divider}` }}>
        {EMAILS.map((e, i) => (
          <Box
            key={e.from}
            sx={{
              display: 'flex', alignItems: 'center', gap: 1.25, p: { xs: 0.75, sm: 1 }, borderRadius: '8px',
              background: i === activeIdx ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
              transition: 'background 0.3s ease', mb: 0.5,
            }}
          >
            <Box sx={{ width: { xs: 28, sm: 32 }, height: { xs: 28, sm: 32 }, borderRadius: '50%', background: e.color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <Typography sx={{ color: '#fff', fontSize: '0.7rem', fontWeight: 700 }}>{e.avatar}</Typography>
            </Box>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography sx={{ fontWeight: i === activeIdx ? 700 : 500, color: 'text.primary', display: 'block', fontSize: '0.75rem', lineHeight: 1.3 }}>
                {e.from}
              </Typography>
              <Typography sx={{ color: 'text.secondary', fontSize: '0.68rem', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {e.subject}
              </Typography>
            </Box>
            <Typography sx={{ color: 'text.disabled', fontSize: '0.65rem', flexShrink: 0 }}>{e.time}</Typography>
          </Box>
        ))}
      </Box>

      {/* AI reply area */}
      <Box sx={{ p: { xs: 1.5, sm: 2 }, minHeight: { xs: 110, sm: 130 } }}>
        <AnimatePresence mode="wait">
          {phase === 'thinking' && (
            <motion.div key="thinking" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                <Box sx={{ width: 22, height: 22, borderRadius: '50%', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <AutoAwesomeRoundedIcon sx={{ fontSize: 12, color: '#fff' }} />
                </Box>
                <Typography sx={{ color: 'primary.main', fontWeight: 600, fontSize: '0.72rem' }}>AI is generating reply…</Typography>
              </Box>
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                {[0, 1, 2].map((i) => (
                  <motion.div key={i} animate={{ y: [0, -4, 0] }} transition={{ repeat: Infinity, duration: 0.7, delay: i * 0.15 }}>
                    <Box sx={{ width: 5, height: 5, borderRadius: '50%', background: theme.palette.primary.main }} />
                  </motion.div>
                ))}
              </Box>
            </motion.div>
          )}

          {phase === 'reply' && showReply && (
            <motion.div key="reply" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.25 }}>
                <Box sx={{ width: 22, height: 22, borderRadius: '50%', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <AutoAwesomeRoundedIcon sx={{ fontSize: 12, color: '#fff' }} />
                </Box>
                <Typography sx={{ color: 'primary.main', fontWeight: 600, fontSize: '0.72rem' }}>AI Reply — ready in 180ms</Typography>
                <CheckCircleRoundedIcon sx={{ fontSize: 13, color: 'success.main', ml: 'auto' }} />
              </Box>
              <Box sx={{ p: 1.25, borderRadius: '8px', background: alpha(theme.palette.primary.main, 0.07), border: `1px solid ${alpha(theme.palette.primary.main, 0.14)}` }}>
                <Typography sx={{ fontSize: '0.74rem', color: 'text.primary', lineHeight: 1.6 }}>
                  {typedText}
                  <Box component="span" sx={{ display: 'inline-block', width: 1.5, height: '0.85em', background: theme.palette.primary.main, ml: '1px', animation: 'blink 1s step-end infinite', '@keyframes blink': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0 } } }} />
                </Typography>
              </Box>
            </motion.div>
          )}

          {phase === 'email' && (
            <motion.div key="email" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <Typography sx={{ color: 'text.disabled', fontSize: '0.72rem' }}>Waiting for new email…</Typography>
            </motion.div>
          )}
        </AnimatePresence>
      </Box>

      {/* Status bar */}
      <Box sx={{ px: { xs: 1.5, sm: 2 }, py: 0.875, borderTop: `1px solid ${theme.palette.divider}`, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: theme.palette.success.main, boxShadow: `0 0 5px ${theme.palette.success.main}`, flexShrink: 0 }} />
        <Typography sx={{ color: 'text.disabled', fontSize: '0.65rem' }}>Live · 1,247 emails/min</Typography>
        <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <BoltRoundedIcon sx={{ fontSize: 11, color: 'warning.main' }} />
          <Typography sx={{ color: 'warning.main', fontSize: '0.65rem', fontWeight: 600 }}>{'<'}25ms</Typography>
        </Box>
      </Box>
    </Box>
  );
}

export default function HeroSection() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  return (
    <Box
      component="section"
      sx={{
        minHeight: '100svh',
        display: 'flex',
        alignItems: 'center',
        // Mobile: less top padding (navbar is 56px), desktop: more breathing room
        pt: { xs: '72px', sm: '80px', md: '88px' },
        pb: { xs: 6, sm: 8, md: 10 },
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Background glow — lighter on mobile for perf */}
      <Box sx={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' }}>
        <Box sx={{
          position: 'absolute', top: '-15%', left: '50%', transform: 'translateX(-50%)',
          width: { xs: '120vw', md: '80vw' }, height: '50vh', borderRadius: '50%',
          background: isDark
            ? 'radial-gradient(ellipse, rgba(129,140,248,0.08) 0%, transparent 70%)'
            : 'radial-gradient(ellipse, rgba(67,56,202,0.05) 0%, transparent 70%)',
        }} />
      </Box>

      <Box
        sx={{
          maxWidth: 1200, mx: 'auto',
          px: { xs: 2, sm: 3, md: 4 },
          width: '100%',
          display: 'flex',
          // Stack on mobile/tablet, side-by-side on large desktop
          flexDirection: { xs: 'column', lg: 'row' },
          alignItems: 'center',
          gap: { xs: 4, sm: 5, lg: 8 },
        }}
      >
        {/* ── Copy ── */}
        <Box sx={{ flex: 1, maxWidth: { lg: 560 }, width: '100%' }}>
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
            <Chip
              icon={<AutoAwesomeRoundedIcon sx={{ fontSize: '13px !important' }} />}
              label="Predictive AI · Replies before you open"
              size="small"
              sx={{
                mb: { xs: 2, sm: 3 },
                fontWeight: 600,
                fontSize: { xs: '0.7rem', sm: '0.75rem' },
                background: alpha(theme.palette.primary.main, isDark ? 0.12 : 0.08),
                color: 'primary.main',
                border: `1px solid ${alpha(theme.palette.primary.main, isDark ? 0.25 : 0.18)}`,
                '& .MuiChip-icon': { color: 'primary.main' },
                height: 28,
              }}
            />
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.08 }}>
            <Typography
              variant="h1"
              sx={{
                mb: { xs: 2, sm: 2.5 },
                // Tighter clamp on mobile — no oversized heading
                fontSize: { xs: 'clamp(1.75rem, 7vw, 2.25rem)', sm: 'clamp(2rem, 5vw, 3rem)', lg: 'clamp(2.5rem, 4vw, 3.5rem)' },
                background: isDark
                  ? 'linear-gradient(135deg, #f8fafc 0%, #cbd5e1 100%)'
                  : 'linear-gradient(135deg, #0f172a 0%, #334155 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              Email replies on{' '}
              <Box component="span" sx={{ background: grad.primary, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                autopilot.
              </Box>
            </Typography>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.16 }}>
            <Typography
              variant="body1"
              sx={{
                color: 'text.secondary',
                mb: { xs: 3, sm: 4 },
                fontSize: { xs: '0.9rem', sm: '1rem' },
                lineHeight: 1.7,
                maxWidth: { sm: 460 },
              }}
            >
              AI generates your replies{' '}
              <Box component="strong" sx={{ color: 'text.primary', fontWeight: 600 }}>
                before you even open the email
              </Box>
              . Sub-25ms processing, smart tone learning, zero-blocking architecture.
            </Typography>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.24 }}>
            <Box
              sx={{
                display: 'flex',
                gap: { xs: 1.25, sm: 1.5 },
                flexDirection: { xs: 'column', sm: 'row' },
                mb: { xs: 3, sm: 4 },
              }}
            >
              <Button
                variant="contained"
                size="large"
                endIcon={<ArrowForwardRoundedIcon />}
                fullWidth={false}
                sx={{
                  background: grad.primary,
                  // Full width on xs so it's easy to tap
                  width: { xs: '100%', sm: 'auto' },
                  minHeight: 48,
                  fontSize: { xs: '0.9rem', sm: '1rem' },
                  px: { xs: 2.5, sm: 3.5 },
                  boxShadow: isDark
                    ? '0 6px 20px rgba(129,140,248,0.28)'
                    : '0 6px 20px rgba(67,56,202,0.22)',
                  '&:hover': { filter: 'brightness(1.08)' },
                }}
              >
                Start for free
              </Button>
              <Button
                variant="outlined"
                size="large"
                sx={{
                  width: { xs: '100%', sm: 'auto' },
                  minHeight: 48,
                  fontSize: { xs: '0.9rem', sm: '1rem' },
                  px: { xs: 2.5, sm: 3 },
                }}
              >
                Watch demo
              </Button>
            </Box>
          </motion.div>

          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.45, delay: 0.35 }}>
            <Box sx={{ display: 'flex', gap: { xs: 2.5, sm: 3 }, flexWrap: 'wrap' }}>
              {[
                { value: '<25ms', label: 'Response time' },
                { value: '10K+', label: 'Concurrent users' },
                { value: '80%',  label: 'Less manual work' },
              ].map((stat) => (
                <Box key={stat.label}>
                  <Typography sx={{ fontWeight: 700, fontSize: { xs: '1rem', sm: '1.1rem' }, color: 'primary.main', lineHeight: 1 }}>
                    {stat.value}
                  </Typography>
                  <Typography sx={{ color: 'text.disabled', fontSize: '0.72rem', mt: 0.25 }}>
                    {stat.label}
                  </Typography>
                </Box>
              ))}
            </Box>
          </motion.div>
        </Box>

        {/* ── Live demo ── */}
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            justifyContent: 'center',
            width: '100%',
            // On mobile the demo sits below copy — constrain it so it doesn't feel too tall
            maxWidth: { xs: '100%', sm: 480, lg: 'none' },
          }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
            style={{ width: '100%', display: 'flex', justifyContent: 'center' }}
          >
            <LiveInboxDemo />
          </motion.div>
        </Box>
      </Box>
    </Box>
  );
}
