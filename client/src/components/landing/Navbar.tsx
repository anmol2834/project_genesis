'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  AppBar, Toolbar, Box, Button, IconButton, useTheme, alpha,
  Drawer, List, ListItemButton, ListItemText, Divider,
} from '@mui/material';
import LightModeRoundedIcon from '@mui/icons-material/LightModeRounded';
import DarkModeRoundedIcon from '@mui/icons-material/DarkModeRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import MenuRoundedIcon from '@mui/icons-material/MenuRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';
import { motion, AnimatePresence } from 'framer-motion';
import NextLink from 'next/link';
import { useThemeMode } from '@/providers/AppThemeProvider';
import { lightGradients, darkGradients } from '@/theme/palette';

const NAV_LINKS = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Features',     href: '#features'     },
  { label: 'Pricing',      href: '#pricing'      },
];

function smoothScroll(href: string, onDone?: () => void) {
  const id = href.replace('#', '');
  const el = document.getElementById(id);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    onDone?.();
  }
}

export default function Navbar() {
  const { mode, toggleTheme } = useThemeMode();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const [scrolled, setScrolled] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeSection, setActiveSection] = useState('');

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Highlight active nav link based on scroll position
  useEffect(() => {
    const ids = NAV_LINKS.map((l) => l.href.replace('#', ''));
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) setActiveSection(`#${entry.target.id}`);
        });
      },
      { rootMargin: '-40% 0px -55% 0px' },
    );
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  const handleNavClick = useCallback((href: string) => {
    smoothScroll(href, () => setDrawerOpen(false));
  }, []);

  return (
    <>
      <AppBar
        position="fixed"
        sx={{
          background: scrolled ? alpha(theme.palette.background.default, 0.88) : 'transparent',
          backdropFilter: scrolled ? 'blur(16px)' : 'none',
          borderBottom: scrolled ? `1px solid ${theme.palette.divider}` : '1px solid transparent',
          transition: 'all 0.3s ease',
          boxShadow: 'none',
        }}
      >
        <Toolbar
          sx={{
            maxWidth: 1200,
            width: '100%',
            mx: 'auto',
            px: { xs: 2, sm: 3, md: 4 },
            minHeight: { xs: 56, sm: 64 },
            justifyContent: 'space-between',
          }}
        >
          {/* Logo */}
          <motion.div initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4 }}>
            <Box
              component="button"
              onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
              sx={{ display: 'flex', alignItems: 'center', gap: 0.75, background: 'none', border: 'none', cursor: 'pointer', p: 0 }}
            >
              <Box
                sx={{
                  width: { xs: 28, sm: 32 }, height: { xs: 28, sm: 32 },
                  borderRadius: '8px', background: grad.primary,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                }}
              >
                <BoltRoundedIcon sx={{ color: '#fff', fontSize: { xs: 15, sm: 18 } }} />
              </Box>
              <Box
                component="span"
                sx={{ fontWeight: 700, fontSize: { xs: '0.95rem', sm: '1.05rem' }, letterSpacing: '-0.02em', color: 'text.primary' }}
              >
                MailFlow<Box component="span" sx={{ color: 'primary.main' }}>AI</Box>
              </Box>
            </Box>
          </motion.div>

          {/* Desktop nav links */}
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 }}>
            <Box sx={{ display: { xs: 'none', md: 'flex' }, gap: 0.5 }}>
              {NAV_LINKS.map((item) => {
                const isActive = activeSection === item.href;
                return (
                  <Button
                    key={item.label}
                    onClick={() => handleNavClick(item.href)}
                    sx={{
                      color: isActive ? 'primary.main' : 'text.secondary',
                      fontWeight: isActive ? 600 : 500,
                      fontSize: '0.875rem',
                      minHeight: 44,
                      position: 'relative',
                      '&:hover': { color: 'text.primary', background: 'transparent' },
                      '&::after': {
                        content: '""',
                        position: 'absolute',
                        bottom: 6,
                        left: '50%',
                        transform: isActive ? 'translateX(-50%) scaleX(1)' : 'translateX(-50%) scaleX(0)',
                        transformOrigin: 'center',
                        width: '60%',
                        height: '2px',
                        borderRadius: '9999px',
                        background: grad.primary,
                        transition: 'transform 0.25s ease',
                      },
                      '&:hover::after': { transform: 'translateX(-50%) scaleX(1)' },
                    }}
                  >
                    {item.label}
                  </Button>
                );
              })}
            </Box>
          </motion.div>

          {/* Actions */}
          <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4, delay: 0.15 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: { xs: 0.5, sm: 1 } }}>
              <IconButton
                onClick={toggleTheme}
                size="small"
                sx={{ color: 'text.secondary', width: 44, height: 44 }}
              >
                {mode === 'dark'
                  ? <LightModeRoundedIcon sx={{ fontSize: 18 }} />
                  : <DarkModeRoundedIcon sx={{ fontSize: 18 }} />
                }
              </IconButton>

              <Button
                component={NextLink}
                href="/sign-in"
                variant="outlined"
                size="small"
                sx={{ display: { xs: 'none', sm: 'flex' }, minHeight: 36 }}
              >
                Sign in
              </Button>

              <Button
                component={NextLink}
                href="/sign-up"
                variant="contained"
                size="small"
                sx={{
                  display: { xs: 'none', sm: 'flex' },
                  background: grad.primary,
                  minHeight: 38,
                  fontSize: '0.875rem',
                  px: 2,
                  '&:hover': { filter: 'brightness(1.08)' },
                }}
              >
                Get started
              </Button>

              {/* Hamburger — mobile only */}
              <IconButton
                onClick={() => setDrawerOpen(true)}
                size="small"
                sx={{ display: { xs: 'flex', md: 'none' }, color: 'text.secondary', width: 44, height: 44 }}
                aria-label="Open menu"
              >
                <MenuRoundedIcon sx={{ fontSize: 22 }} />
              </IconButton>
            </Box>
          </motion.div>
        </Toolbar>
      </AppBar>

      {/* Mobile Drawer */}
      <Drawer
        anchor="right"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        PaperProps={{
          sx: {
            width: 280,
            background: theme.palette.background.default,
            backdropFilter: 'blur(20px)',
            pt: 1,
          },
        }}
      >
        {/* Drawer header */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 2.5, py: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            <Box sx={{ width: 28, height: 28, borderRadius: '8px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <BoltRoundedIcon sx={{ color: '#fff', fontSize: 15 }} />
            </Box>
            <Box component="span" sx={{ fontWeight: 700, fontSize: '0.95rem', letterSpacing: '-0.02em', color: 'text.primary' }}>
              MailFlow<Box component="span" sx={{ color: 'primary.main' }}>AI</Box>
            </Box>
          </Box>
          <IconButton onClick={() => setDrawerOpen(false)} size="small" sx={{ color: 'text.secondary', width: 40, height: 40 }}>
            <CloseRoundedIcon sx={{ fontSize: 20 }} />
          </IconButton>
        </Box>

        <Divider sx={{ mx: 2 }} />

        {/* Nav links */}
        <List sx={{ px: 1.5, pt: 1.5 }}>
          <AnimatePresence>
            {NAV_LINKS.map((item, i) => {
              const isActive = activeSection === item.href;
              return (
                <motion.div
                  key={item.label}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.06, duration: 0.25 }}
                >
                  <ListItemButton
                    onClick={() => handleNavClick(item.href)}
                    sx={{
                      borderRadius: '10px',
                      mb: 0.5,
                      minHeight: 52,
                      background: isActive ? alpha(theme.palette.primary.main, isDark ? 0.12 : 0.07) : 'transparent',
                      '&:hover': { background: alpha(theme.palette.primary.main, isDark ? 0.10 : 0.06) },
                    }}
                  >
                    <ListItemText
                      primary={item.label}
                      primaryTypographyProps={{
                        fontWeight: isActive ? 600 : 500,
                        fontSize: '0.95rem',
                        color: isActive ? 'primary.main' : 'text.primary',
                      }}
                    />
                    {isActive && (
                      <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: grad.primary, flexShrink: 0 }} />
                    )}
                  </ListItemButton>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </List>

        <Divider sx={{ mx: 2, mt: 1 }} />

        {/* Mobile CTA buttons */}
        <Box sx={{ px: 2.5, pt: 2.5, pb: 3, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
          <Button component={NextLink} href="/sign-in" variant="outlined" fullWidth sx={{ minHeight: 48, fontWeight: 500 }}>
            Sign in
          </Button>
          <Button
            component={NextLink}
            href="/sign-up"
            variant="contained"
            fullWidth
            endIcon={<ArrowForwardRoundedIcon />}
            sx={{
              background: grad.primary,
              minHeight: 48,
              fontWeight: 600,
              '&:hover': { filter: 'brightness(1.08)' },
            }}
          >
            Get started free
          </Button>
        </Box>
      </Drawer>
    </>
  );
}
