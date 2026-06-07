'use client';

import { Box, Typography, useTheme } from '@mui/material';
import NextLink from 'next/link';

export default function Footer() {
  const theme = useTheme();

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
          sx={{ display: 'flex', alignItems: 'center', gap: 0, justifyContent: { xs: 'center', sm: 'flex-start' }, textDecoration: 'none', overflow: 'hidden' }}
        >
          <Box component="img" src="/Proxipilot logo.svg" alt="Proxipilot Logo" sx={{ width: 64, height: 64, flexShrink: 0 }} />
          <Typography sx={{ fontWeight: 700, letterSpacing: '-0.02em', color: 'text.primary', fontSize: '0.9rem', ml: -2.5 }}>
            Proxipilot
          </Typography>
        </Box>

        {/* Links */}
        <Box sx={{ display: 'flex', gap: { xs: 2.5, sm: 3 }, flexWrap: 'wrap', justifyContent: 'center' }}>
          {[
            { label: 'Privacy', href: '/privacy' },
            { label: 'Terms', href: '/terms' },
            { label: 'Refund', href: '/refund' },
            { label: 'Docs', href: '/docs' },
            { label: 'Status', href: '/status' },
          ].map((link) => (
            <Typography
              key={link.label}
              component={NextLink}
              href={link.href}
              sx={{
                color: 'text.disabled',
                cursor: 'pointer',
                fontSize: { xs: '0.78rem', sm: '0.8rem' },
                transition: 'color 0.15s',
                textDecoration: 'none',
                lineHeight: '44px',
                '&:hover': { color: 'text.secondary' },
              }}
            >
              {link.label}
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
          © {new Date().getFullYear()} Proxipilot. All rights reserved.
        </Typography>
      </Box>
    </Box>
  );
}
