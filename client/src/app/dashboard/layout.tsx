'use client';

import { Box, IconButton, useTheme } from '@mui/material';
import { useRouter } from 'next/navigation';
import LightModeRoundedIcon from '@mui/icons-material/LightModeRounded';
import DarkModeRoundedIcon from '@mui/icons-material/DarkModeRounded';
import NotificationsRoundedIcon from '@mui/icons-material/NotificationsRounded';
import { useThemeMode } from '@/providers/AppThemeProvider';
import { lightGradients, darkGradients } from '@/theme/palette';
import Sidebar from '@/components/dashboard/Sidebar';
import TopBar from '@/components/dashboard/TopBar';

export default function DashboardShell({ children }: { children: React.ReactNode }) {
  const { mode, toggleTheme } = useThemeMode();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const router = useRouter();
  const grad = isDark ? darkGradients : lightGradients;

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
          alignItems: 'center', justifyContent: 'flex-end', gap: 1,
          px: 3, py: 1.5, flexShrink: 0,
          borderBottom: `1px solid ${theme.palette.divider}`,
          background: isDark ? 'rgba(8,13,24,0.9)' : theme.palette.background.paper,
        }}>
          {/* Notification Icon */}
          <IconButton
            size="small"
            sx={{
              width: 34, height: 34, color: 'text.secondary',
              borderRadius: '8px', border: `1px solid ${theme.palette.divider}`,
              position: 'relative',
              '&:hover': { borderColor: theme.palette.primary.main },
            }}
          >
            <NotificationsRoundedIcon sx={{ fontSize: 16 }} />
            <Box sx={{ position: 'absolute', top: 6, right: 6, width: 7, height: 7, borderRadius: '50%', bgcolor: '#f87171', border: '1.5px solid', borderColor: isDark ? 'rgba(8,13,24,0.9)' : 'background.paper' }} />
          </IconButton>

          {/* Profile Picture */}
          <Box
            onClick={() => router.push('/dashboard/settings')}
            sx={{
              width: 34, height: 34, borderRadius: '8px',
              background: grad.primary,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', fontWeight: 700, fontSize: '0.75rem', color: '#fff',
              border: `1px solid ${theme.palette.divider}`,
              transition: 'transform 0.2s ease',
              '&:hover': { transform: 'scale(1.05)' },
            }}
          >
            JD
          </Box>

          {/* Theme Toggle */}
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
