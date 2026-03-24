'use client';

import { Box, Button, Typography, useTheme, alpha } from '@mui/material';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import { motion } from 'framer-motion';
import { FadeUp } from './motion';
import { lightGradients, darkGradients } from '@/theme/palette';

export default function CTASection() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  return (
    <Box component="section" sx={{ py: { xs: 7, sm: 10, md: 16 }, px: { xs: 2, sm: 3, md: 4 } }}>
      <Box sx={{ maxWidth: 860, mx: 'auto' }}>
        <FadeUp>
          <Box
            sx={{
              borderRadius: { xs: '20px', sm: '28px' },
              // Tighter padding on mobile — 24px, spacious on desktop — 64px
              p: { xs: 3, sm: 5, md: 8 },
              textAlign: 'center',
              position: 'relative',
              overflow: 'hidden',
              background: isDark
                ? 'linear-gradient(135deg, #1e1b4b 0%, #1e293b 50%, #0f172a 100%)'
                : 'linear-gradient(135deg, #eef2ff 0%, #f5f3ff 50%, #ede9fe 100%)',
              border: `1px solid ${alpha(theme.palette.primary.main, isDark ? 0.22 : 0.16)}`,
            }}
          >
            {/* Decorative orbs — smaller on mobile */}
            <Box sx={{ position: 'absolute', top: '-30%', left: '-10%', width: '50%', height: '150%', background: isDark ? 'radial-gradient(ellipse, rgba(129,140,248,0.10) 0%, transparent 60%)' : 'radial-gradient(ellipse, rgba(67,56,202,0.07) 0%, transparent 60%)', pointerEvents: 'none' }} />
            <Box sx={{ position: 'absolute', bottom: '-30%', right: '-10%', width: '50%', height: '150%', background: isDark ? 'radial-gradient(ellipse, rgba(167,139,250,0.08) 0%, transparent 60%)' : 'radial-gradient(ellipse, rgba(124,58,237,0.05) 0%, transparent 60%)', pointerEvents: 'none' }} />

            {/* Floating icon — smaller on mobile */}
            <motion.div
              animate={{ y: [0, -6, 0] }}
              transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
              style={{ display: 'inline-block', marginBottom: 20 }}
            >
              <Box
                sx={{
                  width: { xs: 48, sm: 56, md: 64 },
                  height: { xs: 48, sm: 56, md: 64 },
                  borderRadius: { xs: '14px', sm: '18px' },
                  mx: 'auto',
                  background: grad.primary,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: isDark
                    ? '0 12px 32px rgba(129,140,248,0.30)'
                    : '0 12px 32px rgba(67,56,202,0.22)',
                }}
              >
                <BoltRoundedIcon sx={{ color: '#fff', fontSize: { xs: 24, sm: 28, md: 32 } }} />
              </Box>
            </motion.div>

            <Typography
              variant="h2"
              sx={{
                mb: { xs: 1.5, sm: 2.5 },
                fontSize: { xs: 'clamp(1.4rem, 6vw, 1.9rem)', sm: 'clamp(1.6rem, 4vw, 2.5rem)' },
                background: isDark
                  ? 'linear-gradient(135deg, #f8fafc 0%, #c7d2fe 100%)'
                  : 'linear-gradient(135deg, #0f172a 0%, #3730a3 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              Stop replying manually.
              <br />
              Let AI handle it.
            </Typography>

            <Typography
              variant="body1"
              sx={{
                color: 'text.secondary',
                mb: { xs: 3, sm: 4, md: 5 },
                maxWidth: 440,
                mx: 'auto',
                lineHeight: 1.7,
                fontSize: { xs: '0.875rem', sm: '1rem' },
              }}
            >
              Join teams that process{' '}
              <Box component="strong" sx={{ color: 'text.primary', fontWeight: 600 }}>
                1,000+ emails per minute
              </Box>{' '}
              with zero manual effort.
            </Typography>

            <Box
              sx={{
                display: 'flex',
                gap: { xs: 1.25, sm: 2 },
                justifyContent: 'center',
                flexDirection: { xs: 'column', sm: 'row' },
                alignItems: 'center',
              }}
            >
              <Button
                variant="contained"
                size="large"
                endIcon={<ArrowForwardRoundedIcon />}
                sx={{
                  background: grad.primary,
                  width: { xs: '100%', sm: 'auto' },
                  maxWidth: { xs: 320, sm: 'none' },
                  minHeight: 48,
                  px: { xs: 3, sm: 4 },
                  fontSize: { xs: '0.9rem', sm: '1rem' },
                  boxShadow: isDark
                    ? '0 10px 28px rgba(129,140,248,0.30)'
                    : '0 10px 28px rgba(67,56,202,0.22)',
                  '&:hover': { filter: 'brightness(1.08)', transform: 'translateY(-1px)' },
                  transition: 'all 0.2s ease',
                }}
              >
                Start free — no credit card
              </Button>
              <Button
                variant="outlined"
                size="large"
                sx={{
                  width: { xs: '100%', sm: 'auto' },
                  maxWidth: { xs: 320, sm: 'none' },
                  minHeight: 48,
                  px: { xs: 3, sm: 3.5 },
                  fontSize: { xs: '0.9rem', sm: '1rem' },
                  borderColor: alpha(theme.palette.primary.main, isDark ? 0.40 : 0.35),
                  '&:hover': { borderColor: 'primary.main' },
                }}
              >
                Book a demo
              </Button>
            </Box>

            <Typography
              sx={{
                color: 'text.disabled',
                mt: { xs: 2, sm: 3 },
                display: 'block',
                fontSize: { xs: '0.72rem', sm: '0.75rem' },
              }}
            >
              Free plan · No setup fees · Cancel anytime
            </Typography>
          </Box>
        </FadeUp>
      </Box>
    </Box>
  );
}
