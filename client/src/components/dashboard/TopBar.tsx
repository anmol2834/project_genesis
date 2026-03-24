'use client';

import { Box, Typography, IconButton, useTheme, Drawer, List, ListItemButton, ListItemIcon, ListItemText } from '@mui/material';
import { useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
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
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import ManageSearchRoundedIcon from '@mui/icons-material/ManageSearchRounded';
import StorageRoundedIcon from '@mui/icons-material/StorageRounded';
import NotificationsRoundedIcon from '@mui/icons-material/NotificationsRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import ExtensionRoundedIcon from '@mui/icons-material/ExtensionRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import { useThemeMode } from '@/providers/AppThemeProvider';
import { lightGradients, darkGradients } from '@/theme/palette';

const NAV_ITEMS = [
  { path: '/dashboard',               label: 'Dashboard',      icon: DashboardRoundedIcon },
  { path: '/dashboard/inbox',         label: 'Inbox',          icon: InboxRoundedIcon },
  { path: '/dashboard/campaigns',     label: 'Campaigns',      icon: CampaignRoundedIcon },
  { path: '/dashboard/leads',         label: 'Leads',          icon: PeopleRoundedIcon },
  { path: '/dashboard/accounts',      label: 'Email Accounts', icon: EmailRoundedIcon },
  { path: '/dashboard/automation',    label: 'Automation',     icon: AutoAwesomeRoundedIcon },
  { path: '/dashboard/research',      label: 'Research',       icon: ManageSearchRoundedIcon },
  { path: '/dashboard/my-data',       label: 'My Data',        icon: StorageRoundedIcon },
  { path: '/dashboard/analytics',     label: 'Analytics',      icon: BarChartRoundedIcon },
  { path: '/dashboard/notifications', label: 'Notifications',  icon: NotificationsRoundedIcon },
  { path: '/dashboard/team',          label: 'Team',           icon: GroupsRoundedIcon },
  { path: '/dashboard/integrations',  label: 'Integrations',   icon: ExtensionRoundedIcon },
  { path: '/dashboard/settings',      label: 'Settings',       icon: SettingsRoundedIcon },
];

export default function TopBar() {
  const { mode, toggleTheme } = useThemeMode();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const router = useRouter();
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const isActive = (path: string) =>
    path === '/dashboard' ? pathname === '/dashboard' : pathname.startsWith(path);

  return (
    <>
      <Box sx={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        px: 2, py: 1.5,
        borderBottom: `1px solid ${theme.palette.divider}`,
        background: isDark ? 'rgba(15,10,40,0.9)' : theme.palette.background.paper,
        backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 20,
      }}>
        <IconButton size="small" onClick={() => setDrawerOpen(true)} sx={{ color: 'text.secondary' }}>
          <MenuRoundedIcon sx={{ fontSize: 20 }} />
        </IconButton>

        <Box onClick={() => router.push('/dashboard')} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, cursor: 'pointer' }}>
          <Box sx={{ width: 26, height: 26, borderRadius: '7px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <BoltRoundedIcon sx={{ color: '#fff', fontSize: 14 }} />
          </Box>
          <Typography sx={{ fontWeight: 700, fontSize: '0.88rem', letterSpacing: '-0.02em', color: 'text.primary' }}>
            MailFlow<Box component="span" sx={{ color: 'primary.main' }}>AI</Box>
          </Typography>
        </Box>

        <IconButton onClick={toggleTheme} size="small"
          sx={{ width: 34, height: 34, color: 'text.secondary', borderRadius: '8px', border: `1px solid ${theme.palette.divider}` }}>
          {mode === 'dark' ? <LightModeRoundedIcon sx={{ fontSize: 15 }} /> : <DarkModeRoundedIcon sx={{ fontSize: 15 }} />}
        </IconButton>
      </Box>

      <Drawer anchor="left" open={drawerOpen} onClose={() => setDrawerOpen(false)}
        PaperProps={{ sx: { width: 240, background: isDark ? 'rgba(15,10,40,0.98)' : theme.palette.background.paper } }}>
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
          {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
            const active = isActive(path);
            return (
              <ListItemButton key={path} selected={active}
                onClick={() => { router.push(path); setDrawerOpen(false); }}
                sx={{ borderRadius: '8px', mb: 0.25, py: 0.9 }}>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <Icon sx={{ fontSize: 17, color: active ? 'primary.main' : 'text.secondary' }} />
                </ListItemIcon>
                <ListItemText primary={label}
                  primaryTypographyProps={{ fontSize: '0.82rem', fontWeight: active ? 600 : 400, color: active ? 'primary.main' : 'text.secondary' }} />
              </ListItemButton>
            );
          })}
        </List>
      </Drawer>
    </>
  );
}
