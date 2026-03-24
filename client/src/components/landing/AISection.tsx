'use client';

import { useState } from 'react';
import { Box, Typography, Chip, useTheme, alpha } from '@mui/material';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import PsychologyRoundedIcon from '@mui/icons-material/PsychologyRounded';
import TuneRoundedIcon from '@mui/icons-material/TuneRounded';
import MemoryRoundedIcon from '@mui/icons-material/MemoryRounded';
import { motion, AnimatePresence } from 'framer-motion';
import { FadeUp, StaggerContainer, fadeUp } from './motion';
import { lightGradients, darkGradients } from '@/theme/palette';

const TONES = [
  { id: 'professional', label: 'Professional', color: '#6366f1' },
  { id: 'friendly',     label: 'Friendly',     color: '#10b981' },
  { id: 'empathetic',   label: 'Empathetic',   color: '#f59e0b' },
];

const REPLIES: Record<string, string> = {
  professional: "Thank you for your email. I've reviewed your proposal and would like to schedule a call. Please let me know your availability this week.",
  friendly:     "Hey! Thanks so much for reaching out 😊 I'd love to chat — when are you free for a quick call?",
  empathetic:   "I completely understand your concern. Let me personally look into this and get back to you with a solution by end of day.",
};

const AI_FEATURES = [
  { icon: PsychologyRoundedIcon, title: 'Context Memory',   desc: 'Remembers every conversation across months. Knows your history with each contact.', color: '#6366f1' },
  { icon: TuneRoundedIcon,       title: 'Tone Adaptation',  desc: 'Learns how you communicate with each person and mirrors your natural style.',        color: '#8b5cf6' },
  { icon: MemoryRoundedIcon,     title: 'Intent Detection', desc: 'Classifies urgency, type, and priority before you even see the email.',              color: '#06b6d4' },
];

export default function AISection() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const [activeTone, setActiveTone] = useState('professional');

  return (
    <Box
      component="section"
      sx={{
        py: { xs: 7, sm: 10, md: 14 },
        px: { xs: 2, sm: 3, md: 4 },
        background: isDark
          ? `linear-gradient(180deg, transparent 0%, ${alpha('#818cf8', 0.04)} 50%, transparent 100%)`
          : `linear-gradient(180deg, transparent 0%, ${alpha('#4338ca', 0.03)} 50%, transparent 100%)`,
      }}
    >
      <Box sx={{ maxWidth: 1200, mx: 'auto' }}>
        <FadeUp>
          <Box sx={{ textAlign: 'center', mb: { xs: 5, sm: 7, md: 10 } }}>
            <Typography variant="overline" sx={{ color: 'primary.main', mb: 1, display: 'block' }}>
              AI Intelligence
            </Typography>
            <Typography
              variant="h2"
              sx={{ mb: 1.5, fontSize: { xs: 'clamp(1.5rem, 6vw, 2rem)', md: 'clamp(1.6rem, 4vw, 2.5rem)' } }}
            >
              Smarter than a{' '}
              <Box component="span" sx={{ background: grad.aurora, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                human assistant
              </Box>
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', maxWidth: 420, mx: 'auto', fontSize: { xs: '0.875rem', sm: '1rem' } }}>
              Not just templates. Real contextual intelligence that learns your voice.
            </Typography>
          </Box>
        </FadeUp>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' },
            gap: { xs: 3, sm: 4, lg: 6 },
            alignItems: 'start',
          }}
        >
          {/* Left — interactive tone demo */}
          <FadeUp>
            <Box
              sx={{
                borderRadius: { xs: '14px', sm: '20px' },
                border: `1px solid ${theme.palette.divider}`,
                background: theme.palette.background.paper,
                overflow: 'hidden',
                boxShadow: theme.shadows[3],
              }}
            >
              {/* Incoming email */}
              <Box sx={{ p: { xs: 2, sm: 2.5 }, borderBottom: `1px solid ${theme.palette.divider}` }}>
                <Typography sx={{ color: 'text.disabled', display: 'block', mb: 1.25, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.62rem' }}>
                  Incoming email
                </Typography>
                <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start' }}>
                  <Box sx={{ width: 30, height: 30, borderRadius: '50%', background: '#f59e0b', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <Typography sx={{ color: '#fff', fontSize: '0.7rem', fontWeight: 700 }}>M</Typography>
                  </Box>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography sx={{ fontWeight: 700, color: 'text.primary', display: 'block', fontSize: '0.78rem' }}>mike@enterprise.com</Typography>
                    <Typography sx={{ color: 'text.secondary', lineHeight: 1.6, fontSize: '0.78rem' }}>
                      Hi, I wanted to follow up on the pricing discussion. Can we get a revised quote by Friday?
                    </Typography>
                  </Box>
                </Box>
              </Box>

              {/* Tone selector */}
              <Box sx={{ p: { xs: 2, sm: 2.5 }, borderBottom: `1px solid ${theme.palette.divider}` }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.5 }}>
                  <AutoAwesomeRoundedIcon sx={{ fontSize: 13, color: 'primary.main' }} />
                  <Typography sx={{ color: 'primary.main', fontWeight: 600, fontSize: '0.72rem' }}>
                    AI detected: Follow-up · Medium priority
                  </Typography>
                </Box>
                <Typography sx={{ color: 'text.disabled', display: 'block', mb: 1.25, fontSize: '0.75rem' }}>Select tone:</Typography>
                {/* flexWrap so chips never overflow on 320px */}
                <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                  {TONES.map((t) => (
                    <Chip
                      key={t.id}
                      label={t.label}
                      size="small"
                      onClick={() => setActiveTone(t.id)}
                      sx={{
                        cursor: 'pointer', fontWeight: 600, fontSize: '0.7rem',
                        height: 28,
                        background: activeTone === t.id ? alpha(t.color, isDark ? 0.18 : 0.10) : 'transparent',
                        color: activeTone === t.id ? t.color : 'text.secondary',
                        border: `1px solid ${activeTone === t.id ? alpha(t.color, isDark ? 0.45 : 0.35) : theme.palette.divider}`,
                        transition: 'all 0.2s ease',
                      }}
                    />
                  ))}
                </Box>
              </Box>

              {/* Generated reply */}
              <Box sx={{ p: { xs: 2, sm: 2.5 } }}>
                <Typography sx={{ color: 'text.disabled', display: 'block', mb: 1.25, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.62rem' }}>
                  AI-generated reply
                </Typography>
                <AnimatePresence mode="wait">
                  <motion.div key={activeTone} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={{ duration: 0.22 }}>
                    <Box sx={{ p: { xs: 1.5, sm: 2 }, borderRadius: '10px', background: alpha(theme.palette.primary.main, isDark ? 0.08 : 0.05), border: `1px solid ${alpha(theme.palette.primary.main, isDark ? 0.18 : 0.10)}` }}>
                      <Typography sx={{ fontSize: { xs: '0.78rem', sm: '0.8rem' }, color: 'text.primary', lineHeight: 1.7 }}>
                        {REPLIES[activeTone]}
                      </Typography>
                    </Box>
                  </motion.div>
                </AnimatePresence>
              </Box>
            </Box>
          </FadeUp>

          {/* Right — feature cards */}
          <StaggerContainer>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: { xs: 1.5, sm: 2 } }}>
              {AI_FEATURES.map((f) => {
                const Icon = f.icon;
                return (
                  <motion.div key={f.title} variants={fadeUp}>
                    <Box
                      sx={{
                        p: { xs: 2, sm: 2.5, md: 3 },
                        borderRadius: '12px',
                        border: `1px solid ${theme.palette.divider}`,
                        background: theme.palette.background.paper,
                        display: 'flex', gap: { xs: 1.5, sm: 2 }, alignItems: 'flex-start',
                        transition: 'all 0.2s ease',
                        '&:hover': {
                          borderColor: alpha(f.color, isDark ? 0.45 : 0.30),
                          boxShadow: `0 4px 16px ${alpha(f.color, isDark ? 0.12 : 0.07)}`,
                          transform: 'translateX(3px)',
                        },
                      }}
                    >
                      <Box sx={{ width: { xs: 38, sm: 44 }, height: { xs: 38, sm: 44 }, borderRadius: '10px', background: alpha(f.color, isDark ? 0.15 : 0.09), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <Icon sx={{ color: f.color, fontSize: { xs: 19, sm: 22 } }} />
                      </Box>
                      <Box>
                        <Typography variant="h6" sx={{ mb: 0.4, fontSize: { xs: '0.875rem', sm: '0.95rem' } }}>{f.title}</Typography>
                        <Typography variant="body2" sx={{ color: 'text.secondary', lineHeight: 1.6, fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>{f.desc}</Typography>
                      </Box>
                    </Box>
                  </motion.div>
                );
              })}
            </Box>
          </StaggerContainer>
        </Box>
      </Box>
    </Box>
  );
}
