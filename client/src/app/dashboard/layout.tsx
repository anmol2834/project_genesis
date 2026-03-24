'use client';

import { Box, IconButton, useTheme } from '@mui/material';
import LightModeRoundedIcon from '@mui/icons-material/LightModeRounded';
import DarkModeRoundedIcon from '@mui/icons-material/DarkModeRounded';
import { useThemeMode } from '@/providers/AppThemeProvider';
import Sidebar from '@/components/dashboard/Sidebar';
import TopBar from '@/components/dashboard/TopBar';

export default function DashboardShell({ children }: { children: React.ReactNode }) {
  const { mode, toggleTheme } = useThemeMode();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  return (
    <Box sx={{
      display: 'flex',
      height: '100svh',
      background: isDark ? '#080d18' : theme.palette.background.default,
      overflow: 'hidden',
    }}>
      {/* Desktop sidebar — self-contained, uses usePathname internally */}
      <Box sx={{ display: { xs: 'none', md: 'flex' } }}>
        <Sidebar />
      </Box>

      {/* Main column */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

        {/* Mobile top bar — self-contained, uses usePathname internally */}
        <Box sx={{ display: { xs: 'block', md: 'none' } }}>
          <TopBar />
        </Box>

        {/* Desktop top-right strip */}
        <Box sx={{
          display: { xs: 'none', md: 'flex' },
          alignItems: 'center', justifyContent: 'flex-end',
          px: 3, py: 1.5, flexShrink: 0,
          borderBottom: `1px solid ${theme.palette.divider}`,
          background: isDark ? 'rgba(8,13,24,0.9)' : theme.palette.background.paper,
        }}>
          <IconButton
            onClick={toggleTheme}
            size="small"
            sx={{
              width: 34, height: 34, color: 'text.secondary',
              borderRadius: '8px', border: `1px solid ${theme.palette.divider}`,
              '&:hover': { borderColor: theme.palette.primary.main },
            }}
          >
            {mode === 'dark'
              ? <LightModeRoundedIcon sx={{ fontSize: 15 }} />
              : <DarkModeRoundedIcon sx={{ fontSize: 15 }} />}
          </IconButton>
        </Box>

        {/* Route content fills remaining space */}
        <Box sx={{ flex: 1, overflow: 'hidden', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
}
