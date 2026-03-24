'use client';

import { useState } from 'react';
import { Box, IconButton, useTheme, alpha } from '@mui/material';
import LightModeRoundedIcon from '@mui/icons-material/LightModeRounded';
import DarkModeRoundedIcon from '@mui/icons-material/DarkModeRounded';
import { useThemeMode } from '@/providers/AppThemeProvider';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import WelcomeBanner from './WelcomeBanner';
import StatsOverview from './StatsOverview';
import InboxPreview from './InboxPreview';
import AIActivityPanel from './AIActivityPanel';
import QuickActions from './QuickActions';
import EmailChart from './EmailChart';

export default function DashboardLayout() {
  const { mode, toggleTheme } = useThemeMode();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [activeNav, setActiveNav] = useState('dashboard');

  return (
    <Box sx={{ display: 'flex', height: '100svh', background: isDark ? '#080d18' : theme.palette.background.default, overflow: 'hidden' }}>

      {/* Desktop sidebar */}
      <Box sx={{ display: { xs: 'none', md: 'flex' } }}>
        <Sidebar active={activeNav} onNavigate={setActiveNav} />
      </Box>

      {/* Main content */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

        {/* Mobile top bar */}
        <Box sx={{ display: { xs: 'block', md: 'none' } }}>
          <TopBar active={activeNav} onNavigate={setActiveNav} />
        </Box>

        {/* Desktop top bar strip */}
        <Box sx={{
          display: { xs: 'none', md: 'flex' },
          alignItems: 'center', justifyContent: 'flex-end',
          px: 3, py: 1.5,
          borderBottom: `1px solid ${theme.palette.divider}`,
          background: isDark ? 'rgba(8,13,24,0.9)' : theme.palette.background.paper,
          flexShrink: 0,
        }}>
          <IconButton
            onClick={toggleTheme}
            size="small"
            sx={{ width: 34, height: 34, color: 'text.secondary', borderRadius: '8px', border: `1px solid ${theme.palette.divider}`, '&:hover': { borderColor: theme.palette.primary.main } }}
          >
            {mode === 'dark'
              ? <LightModeRoundedIcon sx={{ fontSize: 15 }} />
              : <DarkModeRoundedIcon sx={{ fontSize: 15 }} />
            }
          </IconButton>
        </Box>

        {/* Scrollable content */}
        <Box
          sx={{
            flex: 1,
            overflowY: 'auto',
            px: { xs: 2, sm: 3 },
            py: { xs: 2, sm: 2.5 },
            '&::-webkit-scrollbar': { width: 4 },
            '&::-webkit-scrollbar-track': { background: 'transparent' },
            '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
          }}
        >
          <Box sx={{ maxWidth: 1200, mx: 'auto', display: 'flex', flexDirection: 'column', gap: 2.5, pb: 4 }}>
            <WelcomeBanner />
            <StatsOverview />

            <EmailChart />
            <QuickActions />

            <Box sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', lg: '1fr 340px' },
              gap: 2,
              alignItems: 'start',
            }}>
              <InboxPreview />
              <AIActivityPanel />
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
