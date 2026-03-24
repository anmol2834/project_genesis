'use client';

import { Box, IconButton, useTheme, alpha, Typography } from '@mui/material';
import LightModeRoundedIcon from '@mui/icons-material/LightModeRounded';
import DarkModeRoundedIcon from '@mui/icons-material/DarkModeRounded';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import { motion } from 'framer-motion';
import NextLink from 'next/link';
import dynamic from 'next/dynamic';
import { useThemeMode } from '@/providers/AppThemeProvider';
import { lightGradients, darkGradients } from '@/theme/palette';
import SignInForm from './SignInForm';

// Lazy-load the heavy visual panel
const AuthVisual = dynamic(() => import('./AuthVisual'), { ssr: false });

export default function SignInPage() {
  const { mode, toggleTheme } = useThemeMode();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  return (
    <Box
      sx={{
        minHeight: '100svh',
        display: 'flex',
        background: theme.palette.background.default,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* ── Left panel: form ─────────────────────────────────────────────── */}
      <Box
        sx={{
          flex: '0 0 auto',
          width: { xs: '100%', md: '50%', lg: '45%' },
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
          zIndex: 1,
        }}
      >
        {/* Top bar */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: { xs: 2.5, sm: 4 },
            py: 2,
            borderBottom: { xs: `1px solid ${theme.palette.divider}`, md: 'none' },
          }}
        >
          {/* Back to home */}
          <Box
            component={NextLink}
            href="/"
            sx={{
              display: 'flex', alignItems: 'center', gap: 0.5,
              color: 'text.secondary', fontSize: '0.78rem', fontWeight: 500,
              textDecoration: 'none',
              transition: 'color 0.18s',
              '&:hover': { color: 'text.primary' },
            }}
          >
            <ArrowBackRoundedIcon sx={{ fontSize: 14 }} />
            Back
          </Box>

          {/* Logo — visible on mobile only (desktop shows in visual panel) */}
          <Box
            sx={{
              display: { xs: 'flex', md: 'none' },
              alignItems: 'center', gap: 0.75,
            }}
          >
            <Box sx={{ width: 26, height: 26, borderRadius: '7px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <BoltRoundedIcon sx={{ color: '#fff', fontSize: 14 }} />
            </Box>
            <Typography sx={{ fontWeight: 700, fontSize: '0.9rem', letterSpacing: '-0.02em', color: 'text.primary' }}>
              MailFlow<Box component="span" sx={{ color: 'primary.main' }}>AI</Box>
            </Typography>
          </Box>

          {/* Theme toggle */}
          <IconButton
            onClick={toggleTheme}
            size="small"
            sx={{ width: 36, height: 36, color: 'text.secondary', borderRadius: '8px', border: `1px solid ${theme.palette.divider}`, '&:hover': { borderColor: theme.palette.primary.main } }}
          >
            {mode === 'dark'
              ? <LightModeRoundedIcon sx={{ fontSize: 15 }} />
              : <DarkModeRoundedIcon sx={{ fontSize: 15 }} />
            }
          </IconButton>
        </Box>

        {/* Form area — centered vertically */}
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            px: { xs: 2.5, sm: 5, md: 6, lg: 8 },
            py: { xs: 4, sm: 5 },
          }}
        >
          <SignInForm />
        </Box>
      </Box>

      {/* ── Right panel: visual ───────────────────────────────────────────── */}
      <Box
        component={motion.div}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.2 }}
        sx={{
          display: { xs: 'none', md: 'flex' },
          flex: 1,
          position: 'relative',
          borderLeft: `1px solid ${theme.palette.divider}`,
          overflow: 'hidden',
        }}
      >
        {/* Subtle grid pattern overlay */}
        <Box
          sx={{
            position: 'absolute', inset: 0, zIndex: 0, pointerEvents: 'none',
            backgroundImage: isDark
              ? `radial-gradient(${alpha('#818cf8', 0.07)} 1px, transparent 1px)`
              : `radial-gradient(${alpha('#4338ca', 0.05)} 1px, transparent 1px)`,
            backgroundSize: '24px 24px',
          }}
        />
        <Box sx={{ position: 'relative', zIndex: 1, width: '100%' }}>
          <AuthVisual />
        </Box>
      </Box>
    </Box>
  );
}
