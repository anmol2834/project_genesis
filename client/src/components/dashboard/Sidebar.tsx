'use client';

import { Box, Typography, Tooltip, useTheme } from '@mui/material';
import { useRouter, usePathname } from 'next/navigation';
import DashboardRoundedIcon from '@mui/icons-material/DashboardRounded';
import InboxRoundedIcon from '@mui/icons-material/InboxRounded';
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import BarChartRoundedIcon from '@mui/icons-material/BarChartRounded';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import NotificationsRoundedIcon from '@mui/icons-material/NotificationsRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import StorageRoundedIcon from '@mui/icons-material/StorageRounded';
import ManageSearchRoundedIcon from '@mui/icons-material/ManageSearchRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import ExtensionRoundedIcon from '@mui/icons-material/ExtensionRounded';
import { lightGradients, darkGradients } from '@/theme/palette';

const NAV_SECTIONS = [
  {
    label: null,
    items: [
      { path: '/dashboard',              label: 'Dashboard',     icon: DashboardRoundedIcon,     badge: null },
      { path: '/dashboard/inbox',        label: 'Inbox',         icon: InboxRoundedIcon,         badge: 12 },
    ],
  },
  {
    label: 'Outreach',
    items: [
      { path: '/dashboard/campaigns',    label: 'Campaigns',     icon: CampaignRoundedIcon,      badge: null },
      { path: '/dashboard/leads',        label: 'Leads',         icon: PeopleRoundedIcon,        badge: null },
      { path: '/dashboard/accounts',     label: 'Email Accounts',icon: EmailRoundedIcon,         badge: null },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { path: '/dashboard/automation',   label: 'Automation',    icon: AutoAwesomeRoundedIcon,   badge: null },
      { path: '/dashboard/research',     label: 'Research',      icon: ManageSearchRoundedIcon,  badge: null },
      { path: '/dashboard/my-data',      label: 'My Data',       icon: StorageRoundedIcon,       badge: null },
    ],
  },
  {
    label: 'Insights',
    items: [
      { path: '/dashboard/analytics',    label: 'Analytics',     icon: BarChartRoundedIcon,      badge: null },
      { path: '/dashboard/notifications',label: 'Notifications', icon: NotificationsRoundedIcon, badge: 3 },
    ],
  },
  {
    label: 'Workspace',
    items: [
      { path: '/dashboard/team',         label: 'Team',          icon: GroupsRoundedIcon,        badge: null },
      { path: '/dashboard/integrations', label: 'Integrations',  icon: ExtensionRoundedIcon,     badge: null },
    ],
  },
];

export default function Sidebar() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const router = useRouter();
  const pathname = usePathname();

  const isActive = (path: string) =>
    path === '/dashboard' ? pathname === '/dashboard' : pathname.startsWith(path);

  return (
    <Box sx={{
      width: 220, flexShrink: 0, height: '100svh',
      display: 'flex', flexDirection: 'column',
      borderRight: `1px solid ${theme.palette.divider}`,
      background: isDark ? 'rgba(15,10,40,0.85)' : theme.palette.background.paper,
      backdropFilter: 'blur(16px)',
      position: 'sticky', top: 0, zIndex: 10,
    }}>
      {/* Logo */}
      <Box sx={{ px: 2.5, py: 2.5, borderBottom: `1px solid ${theme.palette.divider}` }}>
        <Box
          onClick={() => router.push('/dashboard')}
          sx={{ display: 'flex', alignItems: 'center', gap: 1, cursor: 'pointer' }}
        >
          <Box sx={{
            width: 30, height: 30, borderRadius: '8px', background: grad.primary,
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            <BoltRoundedIcon sx={{ color: '#fff', fontSize: 16 }} />
          </Box>
          <Typography sx={{ fontWeight: 700, fontSize: '0.92rem', letterSpacing: '-0.02em', color: 'text.primary' }}>
            MailFlow<Box component="span" sx={{ color: 'primary.main' }}>AI</Box>
          </Typography>
        </Box>
      </Box>

      {/* Nav sections */}
      <Box sx={{ flex: 1, px: 1.5, py: 1.5, display: 'flex', flexDirection: 'column', gap: 0.25, overflowY: 'auto',
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
                <Tooltip key={path} title="" placement="right">
                  <Box
                    onClick={() => router.push(path)}
                    sx={{
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
                    }}
                  >
                    {active && (
                      <Box sx={{
                        position: 'absolute', left: 0, top: '20%', bottom: '20%',
                        width: 3, borderRadius: '0 3px 3px 0', bgcolor: 'primary.main',
                      }} />
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
                </Tooltip>
              );
            })}
          </Box>
        ))}
      </Box>

      {/* Settings */}
      <Box sx={{ px: 1.5, pb: 2.5, borderTop: `1px solid ${theme.palette.divider}`, pt: 1.5 }}>
        <Box
          onClick={() => router.push('/dashboard/settings')}
          sx={{
            display: 'flex', alignItems: 'center', gap: 1.25,
            px: 1.5, py: 0.9, borderRadius: '9px', cursor: 'pointer',
            background: isActive('/dashboard/settings')
              ? isDark ? 'rgba(129,140,248,0.14)' : 'rgba(67,56,202,0.08)'
              : 'transparent',
            transition: 'background 0.18s ease',
            '&:hover': { background: theme.palette.action.hover },
          }}
        >
          <SettingsRoundedIcon sx={{ fontSize: 17, color: isActive('/dashboard/settings') ? 'primary.main' : 'text.secondary' }} />
          <Typography sx={{ fontSize: '0.82rem', fontWeight: isActive('/dashboard/settings') ? 600 : 400, color: isActive('/dashboard/settings') ? 'primary.main' : 'text.secondary' }}>
            Settings
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
