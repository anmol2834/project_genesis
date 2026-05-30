'use client';

import { Box, Button, useTheme, alpha } from '@mui/material';
import { motion } from 'framer-motion';
import RocketLaunchRoundedIcon from '@mui/icons-material/RocketLaunchRounded';
import NextLink from 'next/link';
import { lightGradients, darkGradients } from '@/theme/palette';

const MotionBox = motion(Box);

export default function FloatingWaitlistButton() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  return (
    <MotionBox
      sx={{
        position: 'fixed',
        bottom: { xs: 20, sm: 30 },
        right: { xs: 20, sm: 30 },
        zIndex: 9999,
      }}
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      whileHover={{ scale: 1.05, y: -2 }}
      whileTap={{ scale: 0.95 }}
      transition={{ type: 'spring', stiffness: 400, damping: 17 }}
    >
      <Button
        component={NextLink}
        href="/waitlist"
        variant="contained"
        startIcon={<RocketLaunchRoundedIcon />}
        sx={{
          minHeight: { xs: 52, sm: 56 },
          px: { xs: 2.5, sm: 3.5 },
          fontSize: { xs: '0.9rem', sm: '1rem' },
          fontWeight: 700,
          borderRadius: '50px',
          background: grad.primary,
          boxShadow: isDark
            ? '0 8px 32px rgba(139,92,246,0.4), 0 0 0 1px rgba(139,92,246,0.2)'
            : '0 8px 32px rgba(139,92,246,0.3), 0 0 0 1px rgba(139,92,246,0.1)',
          position: 'relative',
          overflow: 'hidden',
          '&::before': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: '-100%',
            width: '100%',
            height: '100%',
            background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)',
            animation: 'shimmer 3s infinite',
          },
          '&:hover': {
            boxShadow: isDark
              ? '0 12px 40px rgba(139,92,246,0.5), 0 0 0 1px rgba(139,92,246,0.3)'
              : '0 12px 40px rgba(139,92,246,0.4), 0 0 0 1px rgba(139,92,246,0.2)',
          },
        }}
      >
        <Box
          component="span"
          sx={{
            position: 'absolute',
            top: -2,
            right: -2,
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: '#10b981',
            boxShadow: '0 0 12px rgba(16,185,129,0.8)',
            animation: 'pulse 2s ease-in-out infinite',
          }}
        />
        Join Waitlist
      </Button>

      <style jsx global>{`
        @keyframes shimmer {
          0% { left: -100%; }
          100% { left: 200%; }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.7; transform: scale(1.2); }
        }
      `}</style>
    </MotionBox>
  );
}
