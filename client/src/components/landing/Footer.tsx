'use client';

import { Box, Typography, useTheme } from '@mui/material';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import NextLink from 'next/link';
import { lightGradients, darkGradients } from '@/theme/palette';

export default function Footer() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  return (
    <Box
      component="footer"
      sx={{
        borderTop: `1px solid ${theme.palette.divider}`,
        py: { xs: 3, sm: 4 },
        px: { xs: 2, sm: 3, md: 4 },
      }}
    >
      <Box
        sx={{
          maxWidth: 1200,
          mx: 'auto',
          display: 'flex',
          // Stack on mobile, row on sm+
          flexDirection: { xs: 'column', sm: 'row' },
          alignItems: 'center',
          justifyContent: { sm: 'space-between' },
          gap: { xs: 2.5, sm: 2 },
          textAlign: { xs: 'center', sm: 'left' },
        }}
      >
        {/* Brand */}
        <Box
          component={NextLink}
          href="/"
          sx={{ display: 'flex', alignItems: 'center', gap: 0.75, justifyContent: { xs: 'center', sm: 'flex-start' }, textDecoration: 'none' }}
        >
          <Box sx={{ width: 22, height: 22, borderRadius: '6px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <BoltRoundedIcon sx={{ color: '#fff', fontSize: 12 }} />
          </Box>
          <Typography sx={{ fontWeight: 700, letterSpacing: '-0.02em', color: 'text.primary', fontSize: '0.9rem' }}>
            MailFlow<Box component="span" sx={{ color: 'primary.main' }}>AI</Box>
          </Typography>
        </Box>

        {/* Links */}
        <Box sx={{ display: 'flex', gap: { xs: 2.5, sm: 3 }, flexWrap: 'wrap', justifyContent: 'center' }}>
          {['Privacy', 'Terms', 'Docs', 'Status'].map((link) => (
            <Typography
              key={link}
              sx={{
                color: 'text.disabled',
                cursor: 'pointer',
                fontSize: { xs: '0.78rem', sm: '0.8rem' },
                transition: 'color 0.15s',
                // Minimum touch target height
                lineHeight: '44px',
                '&:hover': { color: 'text.secondary' },
              }}
            >
              {link}
            </Typography>
          ))}
        </Box>

        {/* Copyright */}
        <Typography
          sx={{
            color: 'text.disabled',
            fontSize: { xs: '0.72rem', sm: '0.75rem' },
            whiteSpace: 'nowrap',
          }}
        >
          © {new Date().getFullYear()} MailFlowAI. All rights reserved.
        </Typography>
      </Box>
    </Box>
  );
}
