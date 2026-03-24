'use client';

import { Box, Typography, IconButton, useTheme, alpha, Drawer, List, ListItemButton, ListItemIcon, ListItemText } from '@mui/material';
import { useState } from 'react';
import MenuRoundedIcon from '@mui/icons-material/MenuRounded';
import LightModeRoundedIcon from '@mui/icons-material/LightModeRounded';
import DarkModeRoundedIcon from '@mui/icons-material/DarkModeRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import DashboardRoundedIcon from '@mui/icons-material/DashboardRounded';
import InboxRoundedIcon from '@mui/icons-material/InboxRounded';
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import BarChartRoundedIcon from '@mui/icons-material/BarChartRounded';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';
import { useThemeMode } from '@/providers/AppThemeProvider';
import { lightGradients, darkGradients } from '@/theme/palette';

const NAV_ITEMS = [
  { id: 'dashboard',  label: 'Dashboard',  icon: DashboardRoundedIcon },
  { id: 'inbox',      label: 'Inbox',       icon: InboxRoundedIcon },
  { id: 'campaigns',  label: 'Campaigns',   icon: CampaignRoundedIcon },
  { id: 'automation', label: 'Automation',  icon: AutoAwesomeRoundedIcon },
  { id: 'analytics',  label: 'Analytics',   icon: BarChartRoundedIcon },
  { id: 'settings',   label: 'Settings',    icon: SettingsRoundedIcon },
];

interface Props {
  active: string;
  onNavigate: (id: string) => void;
}

export default function TopBar({ active, onNavigate }: Props) {
  const { mode, toggleTheme } = useThemeMode();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <>
      <Box sx={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        px: 2, py: 1.5,
        borderBottom: `1px solid ${theme.palette.divider}`,
        background: isDark ? alpha(theme.palette.background.paper, 0.85) : theme.palette.background.paper,
        backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 20,
      }}>
        {/* Hamburger */}
        <IconButton size="small" onClick={() => setDrawerOpen(true)} sx={{ color: 'text.secondary' }}>
          <MenuRoundedIcon sx={{ fontSize: 20 }} />
        </IconButton>

        {/* Logo */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Box sx={{ width: 26, height: 26, borderRadius: '7px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <BoltRoundedIcon sx={{ color: '#fff', fontSize: 14 }} />
          </Box>
          <Typography sx={{ fontWeight: 700, fontSize: '0.88rem', letterSpacing: '-0.02em', color: 'text.primary' }}>
            MailFlow<Box component="span" sx={{ color: 'primary.main' }}>AI</Box>
          </Typography>
        </Box>

        {/* Theme toggle */}
        <IconButton
          onClick={toggleTheme}
          size="small"
          sx={{ width: 34, height: 34, color: 'text.secondary', borderRadius: '8px', border: `1px solid ${theme.palette.divider}` }}
        >
          {mode === 'dark'
            ? <LightModeRoundedIcon sx={{ fontSize: 15 }} />
            : <DarkModeRoundedIcon sx={{ fontSize: 15 }} />
          }
        </IconButton>
      </Box>

      {/* Mobile drawer */}
      <Drawer
        anchor="left"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        PaperProps={{ sx: { width: 220, background: theme.palette.background.paper } }}
      >
        <Box sx={{ px: 2, py: 2.5, borderBottom: `1px solid ${theme.palette.divider}` }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ width: 28, height: 28, borderRadius: '7px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <BoltRoundedIcon sx={{ color: '#fff', fontSize: 14 }} />
            </Box>
            <Typography sx={{ fontWeight: 700, fontSize: '0.9rem', letterSpacing: '-0.02em', color: 'text.primary' }}>
              MailFlow<Box component="span" sx={{ color: 'primary.main' }}>AI</Box>
            </Typography>
          </Box>
        </Box>
        <List sx={{ px: 1, py: 1.5 }}>
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <ListItemButton
              key={id}
              selected={active === id}
              onClick={() => { onNavigate(id); setDrawerOpen(false); }}
              sx={{ borderRadius: '8px', mb: 0.25, py: 0.9 }}
            >
              <ListItemIcon sx={{ minWidth: 32 }}>
                <Icon sx={{ fontSize: 17, color: active === id ? 'primary.main' : 'text.secondary' }} />
              </ListItemIcon>
              <ListItemText
                primary={label}
                primaryTypographyProps={{ fontSize: '0.82rem', fontWeight: active === id ? 600 : 400, color: active === id ? 'primary.main' : 'text.secondary' }}
              />
            </ListItemButton>
          ))}
        </List>
      </Drawer>
    </>
  );
}
