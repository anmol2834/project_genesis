'use client';

import { Box, Typography, IconButton, useTheme, Drawer } from '@mui/material';
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
import CreditCardRoundedIcon from '@mui/icons-material/CreditCardRounded';
import HelpOutlineRoundedIcon from '@mui/icons-material/HelpOutlineRounded';
import { useThemeMode } from '@/providers/AppThemeProvider';
import { lightGradients, darkGradients } from '@/theme/palette';

// ── Mirrors Sidebar NAV_SECTIONS exactly ─────────────────────────────────────
const NAV_SECTIONS = [
  {
    label: null,
    items: [
      { path: '/dashboard',               label: 'Dashboard',      icon: DashboardRoundedIcon,     badge: null },
      { path: '/dashboard/inbox',         label: 'Inbox',          icon: InboxRoundedIcon,         badge: 12   },
    ],
  },
  {
    label: 'Outreach',
    items: [
      { path: '/dashboard/campaigns',     label: 'Campaigns',      icon: CampaignRoundedIcon,      badge: null },
      { path: '/dashboard/leads',         label: 'Leads',          icon: PeopleRoundedIcon,        badge: null },
      { path: '/dashboard/accounts',      label: 'Email Accounts', icon: EmailRoundedIcon,         badge: null },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { path: '/dashboard/automation',    label: 'Automation',     icon: AutoAwesomeRoundedIcon,   badge: null },
      { path: '/dashboard/research',      label: 'Research',       icon: ManageSearchRoundedIcon,  badge: null },
      { path: '/dashboard/my-data',       label: 'My Data',        icon: StorageRoundedIcon,       badge: null },
    ],
  },
  {
    label: 'Insights',
    items: [
      { path: '/dashboard/analytics',     label: 'Analytics',      icon: BarChartRoundedIcon,      badge: null },
      { path: '/dashboard/notifications', label: 'Notifications',  icon: NotificationsRoundedIcon, badge: 3    },
    ],
  },
  {
    label: 'Workspace',
    items: [
      { path: '/dashboard/team',          label: 'Team',           icon: GroupsRoundedIcon,        badge: null },
      { path: '/dashboard/integrations',  label: 'Integrations',   icon: ExtensionRoundedIcon,     badge: null },
    ],
  },
];

const BOTTOM_ITEMS = [
  { path: '/dashboard/settings', label: 'Settings',       icon: SettingsRoundedIcon,    accentColor: 'primary.main' },
  { path: '/dashboard/billing',  label: 'Billing',        icon: CreditCardRoundedIcon,  accentColor: '#34d399'      },
  { path: '/dashboard/help',     label: 'Help & Support', icon: HelpOutlineRoundedIcon, accentColor: '#fbbf24'      },
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

  const navigate = (path: string) => { router.push(path); setDrawerOpen(false); };

  return (
    <>
      {/* ── Mobile top bar ── */}
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

        <Box onClick={() => navigate('/dashboard')} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, cursor: 'pointer' }}>
          <Box sx={{ width: 26, height: 26, borderRadius: '7px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <BoltRoundedIcon sx={{ color: '#fff', fontSize: 14 }} />
          </Box>
          <Typography sx={{ fontWeight: 700, fontSize: '0.88rem', letterSpacing: '-0.02em', color: 'text.primary' }}>
            MailFlow<Box component="span" sx={{ color: 'primary.main' }}>AI</Box>
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          {/* Notification Icon */}
          <IconButton size="small" sx={{ width: 34, height: 34, color: 'text.secondary', borderRadius: '8px', border: `1px solid ${theme.palette.divider}`, position: 'relative' }}>
            <NotificationsRoundedIcon sx={{ fontSize: 16 }} />
            <Box sx={{ position: 'absolute', top: 6, right: 6, width: 7, height: 7, borderRadius: '50%', bgcolor: '#f87171', border: '1.5px solid', borderColor: isDark ? 'rgba(15,10,40,0.9)' : 'background.paper' }} />
          </IconButton>

          {/* Profile Picture */}
          <Box onClick={() => navigate('/dashboard/settings')} sx={{ width: 34, height: 34, borderRadius: '8px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', fontWeight: 700, fontSize: '0.75rem', color: '#fff', border: `1px solid ${theme.palette.divider}` }}>
            JD
          </Box>

          {/* Theme Toggle */}
          <IconButton onClick={toggleTheme} size="small" sx={{ width: 34, height: 34, color: 'text.secondary', borderRadius: '8px', border: `1px solid ${theme.palette.divider}` }}>
            {mode === 'dark' ? <LightModeRoundedIcon sx={{ fontSize: 15 }} /> : <DarkModeRoundedIcon sx={{ fontSize: 15 }} />}
          </IconButton>
        </Box>
      </Box>

      {/* ── Drawer ── */}
      <Drawer
        anchor="left"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        PaperProps={{
          sx: {
            width: 240,
            display: 'flex', flexDirection: 'column',
            background: isDark ? 'rgba(15,10,40,0.98)' : theme.palette.background.paper,
            borderRight: `1px solid ${theme.palette.divider}`,
          },
        }}
      >
        {/* Logo */}
        <Box sx={{ px: 2.5, py: 2.5, borderBottom: `1px solid ${theme.palette.divider}`, flexShrink: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ width: 28, height: 28, borderRadius: '7px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <BoltRoundedIcon sx={{ color: '#fff', fontSize: 14 }} />
            </Box>
            <Typography sx={{ fontWeight: 700, fontSize: '0.9rem', letterSpacing: '-0.02em', color: 'text.primary' }}>
              MailFlow<Box component="span" sx={{ color: 'primary.main' }}>AI</Box>
            </Typography>
          </Box>
        </Box>

        {/* Scrollable nav sections */}
        <Box sx={{
          flex: 1, px: 1.5, py: 1.5, overflowY: 'auto',
          display: 'flex', flexDirection: 'column', gap: 0.25,
          '&::-webkit-scrollbar': { width: 3 },
          '&::-webkit-scrollbar-thumb': { background: 'rgba(255,255,255,0.1)', borderRadius: 2 },
        }}>
          {NAV_SECTIONS.map((section, si) => (
            <Box key={si} sx={{ mb: 0.5 }}>
              {section.label && (
                <Typography sx={{
                  fontSize: '0.6rem', fontWeight: 700,
                  color: isDark ? 'rgba(255,255,255,0.28)' : 'text.disabled',
                  textTransform: 'uppercase', letterSpacing: '0.1em',
                  px: 1.5, py: 0.75, mt: si > 0 ? 0.5 : 0,
                }}>
                  {section.label}
                </Typography>
              )}
              {section.items.map(({ path, label, icon: Icon, badge }) => {
                const active = isActive(path);
                return (
                  <Box key={path} onClick={() => navigate(path)} sx={{
                    display: 'flex', alignItems: 'center', gap: 1.25,
                    px: 1.5, py: 0.9, borderRadius: '9px',
                    cursor: 'pointer', position: 'relative',
                    background: active
                      ? isDark ? 'rgba(129,140,248,0.14)' : 'rgba(67,56,202,0.08)'
                      : 'transparent',
                    transition: 'background 0.18s ease',
                    '&:hover': {
                      background: active
                        ? isDark ? 'rgba(129,140,248,0.18)' : 'rgba(67,56,202,0.11)'
                        : theme.palette.action.hover,
                    },
                  }}>
                    {active && (
                      <Box sx={{ position: 'absolute', left: 0, top: '20%', bottom: '20%', width: 3, borderRadius: '0 3px 3px 0', bgcolor: 'primary.main' }} />
                    )}
                    <Icon sx={{ fontSize: 17, color: active ? 'primary.main' : 'text.secondary', transition: 'color 0.18s', flexShrink: 0 }} />
                    <Typography sx={{ fontSize: '0.82rem', fontWeight: active ? 600 : 400, color: active ? 'primary.main' : 'text.secondary', transition: 'color 0.18s', flex: 1 }}>
                      {label}
                    </Typography>
                    {badge && (
                      <Box sx={{ minWidth: 18, height: 18, borderRadius: '9px', bgcolor: 'primary.main', display: 'flex', alignItems: 'center', justifyContent: 'center', px: 0.5 }}>
                        <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: '#fff', lineHeight: 1 }}>{badge}</Typography>
                      </Box>
                    )}
                  </Box>
                );
              })}
            </Box>
          ))}
        </Box>

        {/* Bottom items: Settings, Billing, Help — mirrors Sidebar exactly */}
        <Box sx={{ px: 1.5, pb: 2.5, pt: 1.5, borderTop: `1px solid ${theme.palette.divider}`, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 0.25 }}>
          {BOTTOM_ITEMS.map(({ path, label, icon: Icon, accentColor }) => {
            const active = isActive(path);
            return (
              <Box key={path} onClick={() => navigate(path)} sx={{
                display: 'flex', alignItems: 'center', gap: 1.25,
                px: 1.5, py: 0.9, borderRadius: '9px', cursor: 'pointer', position: 'relative',
                background: active
                  ? isDark ? 'rgba(129,140,248,0.14)' : 'rgba(67,56,202,0.08)'
                  : 'transparent',
                transition: 'background 0.18s ease',
                '&:hover': {
                  background: active
                    ? isDark ? 'rgba(129,140,248,0.18)' : 'rgba(67,56,202,0.11)'
                    : theme.palette.action.hover,
                },
              }}>
                {active && (
                  <Box sx={{ position: 'absolute', left: 0, top: '20%', bottom: '20%', width: 3, borderRadius: '0 3px 3px 0', bgcolor: 'primary.main' }} />
                )}
                <Icon sx={{ fontSize: 17, color: active ? accentColor : 'text.secondary', transition: 'color 0.18s', flexShrink: 0 }} />
                <Typography sx={{ fontSize: '0.82rem', fontWeight: active ? 600 : 400, color: active ? accentColor : 'text.secondary', transition: 'color 0.18s' }}>
                  {label}
                </Typography>
              </Box>
            );
          })}
        </Box>
      </Drawer>
    </>
  );
}
