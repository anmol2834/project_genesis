'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import {
  Box, Typography, useTheme, alpha, InputBase,
  IconButton, Tooltip, Button, Modal, Switch, type Theme,
} from '@mui/material';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import PersonRoundedIcon from '@mui/icons-material/PersonRounded';
import AdminPanelSettingsRoundedIcon from '@mui/icons-material/AdminPanelSettingsRounded';
import ShieldRoundedIcon from '@mui/icons-material/ShieldRounded';
import MailOutlineRoundedIcon from '@mui/icons-material/MailOutlineRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import BlockRoundedIcon from '@mui/icons-material/BlockRounded';
import HourglassEmptyRoundedIcon from '@mui/icons-material/HourglassEmptyRounded';
import EditRoundedIcon from '@mui/icons-material/EditRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import MoreHorizRoundedIcon from '@mui/icons-material/MoreHorizRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import KeyboardArrowDownRoundedIcon from '@mui/icons-material/KeyboardArrowDownRounded';
import FilterListRoundedIcon from '@mui/icons-material/FilterListRounded';
import AccessTimeRoundedIcon from '@mui/icons-material/AccessTimeRounded';
import { lightGradients, darkGradients } from '@/theme/palette';
import {
  TEAM_MEMBERS, ACTIVITY_LOG, ROLE_CONFIG, STATUS_CONFIG,
  ALL_PERMISSIONS, PERMISSION_GROUP_CONFIG, ROLE_DEFAULT_PERMISSIONS,
  TeamMember, MemberRole, MemberStatus, ActivityEvent,
} from './teamData';

// ── Animated counter ──────────────────────────────────────────────────────────
function CountUp({ target, suffix = '' }: { target: number; suffix?: string }) {
  const [val, setVal] = useState(0);
  const frame = useRef<number | null>(null);
  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / 1000, 1);
      setVal(Math.round((1 - Math.pow(1 - p, 3)) * target));
      if (p < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => { if (frame.current) cancelAnimationFrame(frame.current); };
  }, [target]);
  return <>{val.toLocaleString()}{suffix}</>;
}

// ── Avatar ────────────────────────────────────────────────────────────────────
function Avatar({ member, size = 34 }: { member: TeamMember; size?: number }) {
  const initials = member.name.split(' ').map(n => n[0]).join('').slice(0, 2);
  return (
    <Box sx={{
      width: size, height: size, borderRadius: `${size * 0.28}px`, flexShrink: 0,
      background: alpha(member.avatarColor, 0.18),
      border: `1.5px solid ${alpha(member.avatarColor, 0.35)}`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <Typography sx={{ fontSize: `${size * 0.3}px`, fontWeight: 800, color: member.avatarColor, lineHeight: 1 }}>
        {initials}
      </Typography>
    </Box>
  );
}

// ── Role badge ────────────────────────────────────────────────────────────────
function RoleBadge({ role, isDark }: { role: MemberRole; isDark: boolean }) {
  const cfg = ROLE_CONFIG[role];
  const Icon = role === 'owner' ? ShieldRoundedIcon : role === 'admin' ? AdminPanelSettingsRoundedIcon : PersonRoundedIcon;
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.4,
      px: 0.7, py: 0.2, borderRadius: '6px',
      background: isDark ? cfg.darkBg : cfg.bg,
      border: `1px solid ${alpha(cfg.color, 0.3)}`,
    }}>
      <Icon sx={{ fontSize: 9, color: cfg.color }} />
      <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: cfg.color, letterSpacing: '0.04em' }}>
        {cfg.label}
      </Typography>
    </Box>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: MemberStatus }) {
  const cfg = STATUS_CONFIG[status];
  const Icon = status === 'active' ? CheckCircleRoundedIcon : status === 'invited' ? HourglassEmptyRoundedIcon : BlockRoundedIcon;
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.4,
      px: 0.65, py: 0.15, borderRadius: '5px',
      background: cfg.bg, border: `1px solid ${alpha(cfg.color, 0.3)}`,
    }}>
      <Icon sx={{
        fontSize: 8, color: cfg.color,
        animation: status === 'active' ? 'pulse 2.5s ease-in-out infinite' : 'none',
        '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.5 } },
      }} />
      <Typography sx={{ fontSize: '0.52rem', fontWeight: 700, color: cfg.color, letterSpacing: '0.04em' }}>
        {cfg.label}
      </Typography>
    </Box>
  );
}

// ── Activity type icon ────────────────────────────────────────────────────────
function ActivityIcon({ type }: { type: ActivityEvent['type'] }) {
  const map = {
    campaign: { Icon: CampaignRoundedIcon, color: '#818cf8' },
    email:    { Icon: EmailRoundedIcon,    color: '#34d399' },
    ai:       { Icon: AutoAwesomeRoundedIcon, color: '#c084fc' },
    lead:     { Icon: PeopleRoundedIcon,   color: '#fbbf24' },
    settings: { Icon: SettingsRoundedIcon, color: '#60a5fa' },
    invite:   { Icon: SendRoundedIcon,     color: '#22d3ee' },
  };
  const { Icon, color } = map[type];
  return (
    <Box sx={{
      width: 26, height: 26, borderRadius: '8px', flexShrink: 0,
      background: alpha(color, 0.14),
      border: `1px solid ${alpha(color, 0.22)}`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <Icon sx={{ fontSize: 13, color }} />
    </Box>
  );
}

// ── Left panel: nav + stats ───────────────────────────────────────────────────
function LeftPanel({
  members, activeFilter, onFilter, isDark, theme,
}: {
  members: TeamMember[];
  activeFilter: MemberRole | MemberStatus | 'all';
  onFilter: (f: MemberRole | MemberStatus | 'all') => void;
  isDark: boolean; theme: Theme;
}) {
  const active    = members.filter(m => m.status === 'active').length;
  const invited   = members.filter(m => m.status === 'invited').length;
  const suspended = members.filter(m => m.status === 'suspended').length;
  const owners    = members.filter(m => m.role === 'owner').length;
  const admins    = members.filter(m => m.role === 'admin').length;
  const mems      = members.filter(m => m.role === 'member').length;

  const totalEmails = members.reduce((s, m) => s + m.emailsSent, 0);
  const totalAI     = members.reduce((s, m) => s + m.aiActionsTriggered, 0);

  type FilterVal = MemberRole | MemberStatus | 'all';

  const navGroups: { label: string; items: { id: FilterVal; label: string; count: number; color: string }[] }[] = [
    {
      label: 'Overview',
      items: [{ id: 'all', label: 'All Members', count: members.length, color: '#818cf8' }],
    },
    {
      label: 'By Status',
      items: [
        { id: 'active',    label: 'Active',    count: active,    color: '#34d399' },
        { id: 'invited',   label: 'Invited',   count: invited,   color: '#60a5fa' },
        { id: 'suspended', label: 'Suspended', count: suspended, color: '#f87171' },
      ],
    },
    {
      label: 'By Role',
      items: [
        { id: 'owner',  label: 'Owners',  count: owners, color: '#818cf8' },
        { id: 'admin',  label: 'Admins',  count: admins, color: '#c084fc' },
        { id: 'member', label: 'Members', count: mems,   color: '#94a3b8' },
      ],
    },
  ];

  return (
    <Box sx={{
      width: { xs: '100%', md: 210 }, flexShrink: 0,
      borderRight: { md: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}` },
      display: 'flex', flexDirection: 'column',
      background: isDark ? 'rgba(255,255,255,0.012)' : alpha(theme.palette.text.primary, 0.01),
    }}>
      {/* Nav */}
      <Box sx={{ flex: 1, overflowY: 'auto', px: 1, pt: 1.5, pb: 1,
        '&::-webkit-scrollbar': { width: 3 },
        '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.15), borderRadius: 2 },
      }}>
        {navGroups.map(group => (
          <Box key={group.label} sx={{ mb: 1.25 }}>
            <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.1em', px: 0.75, mb: 0.5 }}>
              {group.label}
            </Typography>
            {group.items.map(item => {
              const active = activeFilter === item.id;
              return (
                <Box key={item.id} component="button" onClick={() => onFilter(item.id)} sx={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 0.75,
                  px: 0.75, py: 0.6, borderRadius: '8px', border: 'none', cursor: 'pointer',
                  textAlign: 'left', mb: 0.2,
                  background: active ? isDark ? alpha(item.color, 0.14) : alpha(item.color, 0.09) : 'transparent',
                  transition: 'all 0.15s ease',
                  '&:hover': {
                    background: active
                      ? isDark ? alpha(item.color, 0.18) : alpha(item.color, 0.12)
                      : isDark ? 'rgba(255,255,255,0.04)' : alpha(theme.palette.text.primary, 0.03),
                  },
                }}>
                  <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: item.color, flexShrink: 0, opacity: active ? 1 : 0.4 }} />
                  <Typography sx={{ fontSize: '0.75rem', fontWeight: active ? 700 : 500, color: active ? item.color : 'text.secondary', flex: 1 }}>
                    {item.label}
                  </Typography>
                  {item.count > 0 && (
                    <Box sx={{
                      minWidth: 18, height: 16, px: 0.5, borderRadius: '5px',
                      background: active ? alpha(item.color, isDark ? 0.22 : 0.14) : isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.06),
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: active ? item.color : 'text.disabled', lineHeight: 1 }}>{item.count}</Typography>
                    </Box>
                  )}
                </Box>
              );
            })}
          </Box>
        ))}
      </Box>

      {/* Bottom: team output stats */}
      <Box sx={{
        mx: 1.5, mb: 1.5, p: 1.25, borderRadius: '10px',
        background: isDark ? 'rgba(129,140,248,0.07)' : alpha('#818cf8', 0.05),
        border: `1px solid ${alpha('#818cf8', isDark ? 0.18 : 0.14)}`,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.9 }}>
          <BoltRoundedIcon sx={{ fontSize: 11, color: '#818cf8' }} />
          <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: '#818cf8' }}>Team Output</Typography>
        </Box>
        {[
          { label: 'Emails sent',    value: totalEmails, color: '#34d399' },
          { label: 'AI actions',     value: totalAI,     color: '#c084fc' },
        ].map(({ label, value, color }) => (
          <Box key={label} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
            <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>{label}</Typography>
            <Typography sx={{ fontSize: '0.72rem', fontWeight: 800, color }}>{value.toLocaleString()}</Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

// ── Member row (table row) ────────────────────────────────────────────────────
function MemberRow({ member, isDark, theme, index, onEdit, isCurrentUser }: {
  member: TeamMember; isDark: boolean; theme: Theme; index: number;
  onEdit: (m: TeamMember) => void; isCurrentUser: boolean;
}) {
  const permCount = member.permissions.length;
  const totalPerms = 12;

  return (
    <Box sx={{
      display: 'grid',
      gridTemplateColumns: '1fr 130px 90px 90px 100px 80px',
      alignItems: 'center', gap: 1.5,
      px: 1.75, py: 1.1,
      borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : theme.palette.divider}`,
      transition: 'background 0.12s ease',
      '&:hover': { background: isDark ? 'rgba(255,255,255,0.025)' : alpha(theme.palette.text.primary, 0.02) },
      animation: `rowIn 0.22s ease-out ${index * 0.04}s both`,
      '@keyframes rowIn': { from: { opacity: 0, transform: 'translateX(-4px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
    }}>
      {/* Name + email */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.1, minWidth: 0 }}>
        <Box sx={{ position: 'relative', flexShrink: 0 }}>
          <Avatar member={member} size={34} />
          {member.status === 'active' && (
            <Box sx={{
              position: 'absolute', bottom: -1, right: -1,
              width: 8, height: 8, borderRadius: '50%',
              background: '#34d399',
              border: `1.5px solid ${isDark ? '#080d18' : '#fff'}`,
            }} />
          )}
        </Box>
        <Box sx={{ minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {member.name}
            </Typography>
            {isCurrentUser && (
              <Box sx={{ px: 0.5, py: 0.1, borderRadius: '4px', background: isDark ? 'rgba(129,140,248,0.15)' : alpha('#818cf8', 0.1), border: `1px solid ${alpha('#818cf8', 0.25)}` }}>
                <Typography sx={{ fontSize: '0.48rem', fontWeight: 700, color: '#818cf8' }}>YOU</Typography>
              </Box>
            )}
          </Box>
          <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {member.email}
          </Typography>
        </Box>
      </Box>

      {/* Role */}
      <RoleBadge role={member.role} isDark={isDark} />

      {/* Status */}
      <StatusBadge status={member.status} />

      {/* Permissions */}
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.3 }}>
          <Box sx={{ flex: 1, height: 3, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)', overflow: 'hidden' }}>
            <Box sx={{
              height: '100%', borderRadius: 2,
              width: `${(permCount / totalPerms) * 100}%`,
              background: member.role === 'owner' ? '#818cf8' : member.role === 'admin' ? '#c084fc' : '#94a3b8',
              transition: 'width 0.9s ease',
            }} />
          </Box>
          <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: 'text.disabled', minWidth: 20 }}>{permCount}/{totalPerms}</Typography>
        </Box>
        <Typography sx={{ fontSize: '0.58rem', color: 'text.disabled' }}>permissions</Typography>
      </Box>

      {/* Last active */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
        <AccessTimeRoundedIcon sx={{ fontSize: 10, color: 'text.disabled', flexShrink: 0 }} />
        <Typography sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>{member.lastActive}</Typography>
      </Box>

      {/* Actions */}
      <Box sx={{ display: 'flex', gap: 0.25, justifyContent: 'flex-end' }}>
        <Tooltip title="Edit member" placement="top">
          <IconButton size="small" onClick={() => onEdit(member)} sx={{
            width: 26, height: 26, borderRadius: '6px', color: 'text.secondary',
            '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) },
          }}>
            <EditRoundedIcon sx={{ fontSize: 13 }} />
          </IconButton>
        </Tooltip>
        {!isCurrentUser && (
          <Tooltip title={member.status === 'suspended' ? 'Reactivate' : 'Suspend'} placement="top">
            <IconButton size="small" sx={{
              width: 26, height: 26, borderRadius: '6px', color: 'text.secondary',
              '&:hover': { background: member.status === 'suspended' ? 'rgba(52,211,153,0.1)' : 'rgba(251,191,36,0.1)', color: member.status === 'suspended' ? '#34d399' : '#fbbf24' },
            }}>
              <BlockRoundedIcon sx={{ fontSize: 13 }} />
            </IconButton>
          </Tooltip>
        )}
        {!isCurrentUser && (
          <Tooltip title="Remove member" placement="top">
            <IconButton size="small" sx={{
              width: 26, height: 26, borderRadius: '6px', color: 'text.secondary',
              '&:hover': { background: 'rgba(239,68,68,0.1)', color: '#ef4444' },
            }}>
              <DeleteOutlineRoundedIcon sx={{ fontSize: 13 }} />
            </IconButton>
          </Tooltip>
        )}
      </Box>
    </Box>
  );
}

// ── Mobile member card ────────────────────────────────────────────────────────
function MemberCard({ member, isDark, theme, index, onEdit, isCurrentUser }: {
  member: TeamMember; isDark: boolean; theme: Theme; index: number;
  onEdit: (m: TeamMember) => void; isCurrentUser: boolean;
}) {
  const roleCfg = ROLE_CONFIG[member.role];
  return (
    <Box sx={{
      px: 1.5, py: 1.25,
      borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : theme.palette.divider}`,
      display: 'flex', alignItems: 'center', gap: 1.25,
      transition: 'background 0.12s ease',
      '&:hover': { background: isDark ? 'rgba(255,255,255,0.025)' : alpha(theme.palette.text.primary, 0.02) },
      animation: `rowIn 0.22s ease-out ${index * 0.04}s both`,
      '@keyframes rowIn': { from: { opacity: 0, transform: 'translateX(-4px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
    }}>
      <Box sx={{ position: 'relative', flexShrink: 0 }}>
        <Avatar member={member} size={38} />
        {member.status === 'active' && (
          <Box sx={{ position: 'absolute', bottom: -1, right: -1, width: 9, height: 9, borderRadius: '50%', background: '#34d399', border: `1.5px solid ${isDark ? '#080d18' : '#fff'}` }} />
        )}
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.3 }}>
          <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {member.name}
          </Typography>
          {isCurrentUser && (
            <Box sx={{ px: 0.5, py: 0.1, borderRadius: '4px', background: isDark ? 'rgba(129,140,248,0.15)' : alpha('#818cf8', 0.1), border: `1px solid ${alpha('#818cf8', 0.25)}` }}>
              <Typography sx={{ fontSize: '0.48rem', fontWeight: 700, color: '#818cf8' }}>YOU</Typography>
            </Box>
          )}
        </Box>
        <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mb: 0.5 }}>{member.email}</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
          <RoleBadge role={member.role} isDark={isDark} />
          <StatusBadge status={member.status} />
        </Box>
      </Box>
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 0.5, flexShrink: 0 }}>
        <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>{member.lastActive}</Typography>
        <Box sx={{ display: 'flex', gap: 0.25 }}>
          <IconButton size="small" onClick={() => onEdit(member)} sx={{ width: 26, height: 26, borderRadius: '6px', color: 'text.secondary', '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) } }}>
            <EditRoundedIcon sx={{ fontSize: 13 }} />
          </IconButton>
          {!isCurrentUser && (
            <IconButton size="small" sx={{ width: 26, height: 26, borderRadius: '6px', color: 'text.secondary', '&:hover': { background: 'rgba(239,68,68,0.1)', color: '#ef4444' } }}>
              <DeleteOutlineRoundedIcon sx={{ fontSize: 13 }} />
            </IconButton>
          )}
        </Box>
      </Box>
    </Box>
  );
}

// ── Edit member panel (slide-in overlay) ─────────────────────────────────────
function EditMemberPanel({ member, isDark, theme, onClose }: {
  member: TeamMember; isDark: boolean; theme: Theme; onClose: () => void;
}) {
  const [role, setRole] = useState<MemberRole>(member.role);
  const [perms, setPerms] = useState<Set<string>>(new Set(member.permissions));

  const togglePerm = (key: string) => {
    if (role === 'owner') return; // owner always has all
    setPerms(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const handleRoleChange = (r: MemberRole) => {
    setRole(r);
    setPerms(new Set(ROLE_DEFAULT_PERMISSIONS[r]));
  };

  const groups = ['outreach', 'intelligence', 'workspace'] as const;

  return (
    <Box sx={{
      position: 'fixed', inset: 0, zIndex: 1300,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)', p: 2,
    }} onClick={onClose}>
      <Box sx={{
        width: '100%', maxWidth: 520, maxHeight: '88vh',
        borderRadius: '18px', overflow: 'hidden',
        background: isDark ? '#0f172a' : '#fff',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
        boxShadow: isDark ? '0 32px 80px rgba(0,0,0,0.7)' : '0 32px 80px rgba(15,23,42,0.18)',
        display: 'flex', flexDirection: 'column',
        animation: 'panelIn 0.22s ease-out',
        '@keyframes panelIn': { from: { opacity: 0, transform: 'scale(0.96) translateY(10px)' }, to: { opacity: 1, transform: 'scale(1) translateY(0)' } },
      }} onClick={e => e.stopPropagation()}>

        {/* Header */}
        <Box sx={{
          px: 2.5, pt: 2.25, pb: 1.75,
          borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
            <Avatar member={member} size={38} />
            <Box>
              <Typography sx={{ fontSize: '0.95rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em' }}>{member.name}</Typography>
              <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled' }}>{member.email}</Typography>
            </Box>
          </Box>
          <IconButton size="small" onClick={onClose} sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary', '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) } }}>
            <CloseRoundedIcon sx={{ fontSize: 15 }} />
          </IconButton>
        </Box>

        {/* Scrollable body */}
        <Box sx={{ flex: 1, overflowY: 'auto', p: 2.5,
          '&::-webkit-scrollbar': { width: 4 },
          '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
        }}>
          {/* Role selector */}
          <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.08em', mb: 1 }}>
            Role
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 0.75, mb: 2.5 }}>
            {(['owner', 'admin', 'member'] as MemberRole[]).map(r => {
              const cfg = ROLE_CONFIG[r];
              const active = role === r;
              const Icon = r === 'owner' ? ShieldRoundedIcon : r === 'admin' ? AdminPanelSettingsRoundedIcon : PersonRoundedIcon;
              return (
                <Box key={r} component="button" onClick={() => handleRoleChange(r)} sx={{
                  display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 0.5,
                  p: 1.25, borderRadius: '10px', cursor: 'pointer', textAlign: 'left', border: 'none',
                  background: active ? isDark ? alpha(cfg.color, 0.14) : alpha(cfg.color, 0.09) : isDark ? 'rgba(255,255,255,0.03)' : alpha(theme.palette.text.primary, 0.02),
                  border: `1.5px solid ${active ? alpha(cfg.color, 0.4) : isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
                  transition: 'all 0.15s ease',
                  '&:hover': { borderColor: alpha(cfg.color, 0.4) },
                }}>
                  <Icon sx={{ fontSize: 16, color: active ? cfg.color : 'text.disabled' }} />
                  <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: active ? cfg.color : 'text.secondary' }}>{cfg.label}</Typography>
                  <Typography sx={{ fontSize: '0.58rem', color: 'text.disabled', lineHeight: 1.4 }}>{cfg.description}</Typography>
                </Box>
              );
            })}
          </Box>

          {/* Permissions */}
          <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.08em', mb: 1 }}>
            Permissions
          </Typography>
          {role === 'owner' && (
            <Box sx={{ px: 1.25, py: 0.9, borderRadius: '9px', mb: 1.5, background: isDark ? 'rgba(129,140,248,0.07)' : alpha('#818cf8', 0.05), border: `1px solid ${alpha('#818cf8', 0.2)}` }}>
              <Typography sx={{ fontSize: '0.68rem', color: isDark ? '#818cf8' : '#4338ca', fontWeight: 500 }}>
                Owners have full access to all features and cannot be restricted.
              </Typography>
            </Box>
          )}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {groups.map(group => {
              const groupCfg = PERMISSION_GROUP_CONFIG[group];
              const groupPerms = ALL_PERMISSIONS.filter(p => p.group === group);
              return (
                <Box key={group}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6, mb: 0.75 }}>
                    <Box sx={{ width: 3, height: 14, borderRadius: 2, background: groupCfg.color, flexShrink: 0 }} />
                    <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: groupCfg.color }}>{groupCfg.label}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                    {groupPerms.map((perm, i) => {
                      const enabled = role === 'owner' || perms.has(perm.key);
                      return (
                        <Box key={perm.key} sx={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          py: 0.75, px: 0.5,
                          borderBottom: i < groupPerms.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : theme.palette.divider}` : 'none',
                          '&:hover': { background: isDark ? 'rgba(255,255,255,0.02)' : alpha(theme.palette.text.primary, 0.015), borderRadius: '6px' },
                          transition: 'background 0.12s ease',
                        }}>
                          <Box>
                            <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: enabled ? 'text.primary' : 'text.disabled' }}>{perm.label}</Typography>
                            <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', mt: 0.1 }}>{perm.description}</Typography>
                          </Box>
                          <Switch
                            size="small"
                            checked={enabled}
                            disabled={role === 'owner'}
                            onChange={() => togglePerm(perm.key)}
                            sx={{
                              '& .MuiSwitch-switchBase.Mui-checked': { color: groupCfg.color },
                              '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { backgroundColor: groupCfg.color },
                            }}
                          />
                        </Box>
                      );
                    })}
                  </Box>
                </Box>
              );
            })}
          </Box>
        </Box>

        {/* Footer */}
        <Box sx={{
          px: 2.5, py: 1.5,
          borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
          display: 'flex', gap: 0.75, justifyContent: 'flex-end',
        }}>
          <Button size="small" onClick={onClose} sx={{
            fontSize: '0.72rem', fontWeight: 600, px: 1.5, py: 0.6, borderRadius: '8px', textTransform: 'none',
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.12)' : theme.palette.divider}`,
            color: 'text.primary', background: 'transparent',
            '&:hover': { background: isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.04) },
          }}>Cancel</Button>
          <Button size="small" sx={{
            fontSize: '0.72rem', fontWeight: 700, px: 1.75, py: 0.6, borderRadius: '8px', textTransform: 'none',
            background: isDark ? darkGradients.primary : lightGradients.primary, color: '#fff',
            '&:hover': { opacity: 0.88 },
          }}>Save Changes</Button>
        </Box>
      </Box>
    </Box>
  );
}

// ── Invite modal ──────────────────────────────────────────────────────────────
function InviteModal({ open, onClose, isDark, theme }: {
  open: boolean; onClose: () => void; isDark: boolean; theme: Theme;
}) {
  const [role, setRole] = useState<MemberRole>('member');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [perms, setPerms] = useState<Set<string>>(new Set(ROLE_DEFAULT_PERMISSIONS.member));

  const handleRoleChange = (r: MemberRole) => {
    setRole(r);
    setPerms(new Set(ROLE_DEFAULT_PERMISSIONS[r]));
  };

  const inputSx = {
    px: 1.25, py: 0.85, borderRadius: '9px', fontSize: '0.8rem',
    color: 'text.primary', flex: 1,
    background: isDark ? 'rgba(255,255,255,0.04)' : alpha(theme.palette.text.primary, 0.03),
    border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
    '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 },
    '&:focus-within': { borderColor: isDark ? 'rgba(129,140,248,0.5)' : alpha(theme.palette.primary.main, 0.5) },
    transition: 'border-color 0.15s ease',
  };

  return (
    <Modal open={open} onClose={onClose} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
      <Box sx={{
        width: '100%', maxWidth: 460,
        borderRadius: '18px',
        background: isDark ? '#0f172a' : '#fff',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
        boxShadow: isDark ? '0 32px 80px rgba(0,0,0,0.6)' : '0 32px 80px rgba(15,23,42,0.15)',
        overflow: 'hidden',
        animation: 'modalIn 0.22s ease-out',
        '@keyframes modalIn': { from: { opacity: 0, transform: 'scale(0.96) translateY(8px)' }, to: { opacity: 1, transform: 'scale(1) translateY(0)' } },
      }}>
        {/* Header */}
        <Box sx={{
          px: 2.5, pt: 2.25, pb: 1.75,
          borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
        }}>
          <Box>
            <Typography sx={{ fontSize: '1rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em' }}>Invite Team Member</Typography>
            <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', mt: 0.3 }}>Send an invite link via email</Typography>
          </Box>
          <IconButton size="small" onClick={onClose} sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary', '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) } }}>
            <CloseRoundedIcon sx={{ fontSize: 15 }} />
          </IconButton>
        </Box>

        <Box sx={{ p: 2.5, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {/* Email */}
          <Box>
            <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Email Address</Typography>
            <InputBase placeholder="colleague@company.com" sx={inputSx} fullWidth />
          </Box>

          {/* Role */}
          <Box>
            <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.75 }}>Role</Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 0.75 }}>
              {(['owner', 'admin', 'member'] as MemberRole[]).map(r => {
                const cfg = ROLE_CONFIG[r];
                const active = role === r;
                const Icon = r === 'owner' ? ShieldRoundedIcon : r === 'admin' ? AdminPanelSettingsRoundedIcon : PersonRoundedIcon;
                return (
                  <Box key={r} component="button" onClick={() => handleRoleChange(r)} sx={{
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.4,
                    p: 1, borderRadius: '10px', cursor: 'pointer', border: 'none',
                    background: active ? isDark ? alpha(cfg.color, 0.14) : alpha(cfg.color, 0.09) : isDark ? 'rgba(255,255,255,0.03)' : alpha(theme.palette.text.primary, 0.02),
                    border: `1.5px solid ${active ? alpha(cfg.color, 0.4) : isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
                    transition: 'all 0.15s ease',
                    '&:hover': { borderColor: alpha(cfg.color, 0.35) },
                  }}>
                    <Icon sx={{ fontSize: 18, color: active ? cfg.color : 'text.disabled' }} />
                    <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, color: active ? cfg.color : 'text.secondary' }}>{cfg.label}</Typography>
                  </Box>
                );
              })}
            </Box>
          </Box>

          {/* Advanced permissions toggle */}
          <Box component="button" onClick={() => setShowAdvanced(v => !v)} sx={{
            display: 'flex', alignItems: 'center', gap: 0.5, border: 'none', cursor: 'pointer',
            background: 'transparent', color: isDark ? '#818cf8' : theme.palette.primary.main, p: 0,
          }}>
            <KeyboardArrowDownRoundedIcon sx={{ fontSize: 14, transform: showAdvanced ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }} />
            <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, color: 'inherit' }}>
              {showAdvanced ? 'Hide' : 'Customize'} permissions
            </Typography>
          </Box>

          {showAdvanced && (
            <Box sx={{
              borderRadius: '10px', overflow: 'hidden',
              border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
              animation: 'slideDown 0.2s ease-out',
              '@keyframes slideDown': { from: { opacity: 0, transform: 'translateY(-6px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
            }}>
              {ALL_PERMISSIONS.map((perm, i) => {
                const enabled = role === 'owner' || perms.has(perm.key);
                const groupColor = PERMISSION_GROUP_CONFIG[perm.group].color;
                return (
                  <Box key={perm.key} sx={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    px: 1.25, py: 0.65,
                    borderBottom: i < ALL_PERMISSIONS.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : theme.palette.divider}` : 'none',
                  }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                      <Box sx={{ width: 5, height: 5, borderRadius: '50%', background: groupColor, flexShrink: 0 }} />
                      <Typography sx={{ fontSize: '0.72rem', fontWeight: 500, color: enabled ? 'text.primary' : 'text.disabled' }}>{perm.label}</Typography>
                    </Box>
                    <Switch
                      size="small"
                      checked={enabled}
                      disabled={role === 'owner'}
                      onChange={() => {
                        if (role === 'owner') return;
                        setPerms(prev => { const n = new Set(prev); n.has(perm.key) ? n.delete(perm.key) : n.add(perm.key); return n; });
                      }}
                      sx={{
                        '& .MuiSwitch-switchBase.Mui-checked': { color: groupColor },
                        '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { backgroundColor: groupColor },
                      }}
                    />
                  </Box>
                );
              })}
            </Box>
          )}

          {/* Send button */}
          <Box component="button" sx={{
            width: '100%', border: 'none', cursor: 'pointer', py: 0.95, borderRadius: '10px',
            background: isDark ? darkGradients.primary : lightGradients.primary,
            color: '#fff', fontSize: '0.8rem', fontWeight: 700,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.75,
            transition: 'opacity 0.15s ease', '&:hover': { opacity: 0.88 },
          }}>
            <SendRoundedIcon sx={{ fontSize: 15 }} />
            Send Invite
          </Box>
        </Box>
      </Box>
    </Modal>
  );
}

// ── Activity feed ─────────────────────────────────────────────────────────────
function ActivityFeed({ isDark, theme, filterMemberId }: {
  isDark: boolean; theme: Theme; filterMemberId?: string;
}) {
  const events = filterMemberId
    ? ACTIVITY_LOG.filter(e => e.memberId === filterMemberId)
    : ACTIVITY_LOG;

  return (
    <Box sx={{
      borderRadius: '14px', overflow: 'hidden',
      border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
      background: isDark ? 'rgba(255,255,255,0.02)' : theme.palette.background.paper,
    }}>
      <Box sx={{
        px: 1.75, py: 1.1,
        borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
        display: 'flex', alignItems: 'center', gap: 0.75,
        background: isDark ? 'rgba(129,140,248,0.04)' : alpha('#818cf8', 0.03),
      }}>
        <BoltRoundedIcon sx={{ fontSize: 13, color: '#818cf8' }} />
        <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: 'text.primary' }}>Recent Activity</Typography>
        <Box sx={{ ml: 'auto', px: 0.65, py: 0.15, borderRadius: '5px', background: isDark ? 'rgba(129,140,248,0.15)' : alpha('#818cf8', 0.08), border: `1px solid ${alpha('#818cf8', 0.25)}` }}>
          <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: '#818cf8' }}>Live</Typography>
        </Box>
      </Box>
      <Box sx={{ p: 0 }}>
        {events.map((event, i) => (
          <Box key={event.id} sx={{
            display: 'flex', alignItems: 'flex-start', gap: 1.1,
            px: 1.75, py: 1,
            borderBottom: i < events.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : theme.palette.divider}` : 'none',
            transition: 'background 0.12s ease',
            '&:hover': { background: isDark ? 'rgba(255,255,255,0.02)' : alpha(theme.palette.text.primary, 0.015) },
            animation: `rowIn 0.22s ease-out ${i * 0.04}s both`,
            '@keyframes rowIn': { from: { opacity: 0, transform: 'translateX(-4px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
          }}>
            <ActivityIcon type={event.type} />
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5, flexWrap: 'wrap' }}>
                <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: 'text.primary', flexShrink: 0 }}>
                  {event.memberName}
                </Typography>
                <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
                  {event.action}
                </Typography>
              </Box>
              <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mt: 0.15, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {event.target}
              </Typography>
            </Box>
            <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled', flexShrink: 0, mt: 0.1 }}>{event.timestamp}</Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function TeamPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients.primary : lightGradients.primary;

  const [activeFilter, setActiveFilter] = useState<MemberRole | MemberStatus | 'all'>('all');
  const [search, setSearch] = useState('');
  const [editMember, setEditMember] = useState<TeamMember | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'members' | 'activity'>('members');

  const currentUserId = 'm1'; // simulated logged-in user

  const filtered = useMemo(() => {
    return TEAM_MEMBERS.filter(m => {
      if (activeFilter !== 'all') {
        if (['owner', 'admin', 'member'].includes(activeFilter) && m.role !== activeFilter) return false;
        if (['active', 'invited', 'suspended'].includes(activeFilter) && m.status !== activeFilter) return false;
      }
      if (search) {
        const q = search.toLowerCase();
        return m.name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q);
      }
      return true;
    });
  }, [activeFilter, search]);

  const totalActive  = TEAM_MEMBERS.filter(m => m.status === 'active').length;
  const totalInvited = TEAM_MEMBERS.filter(m => m.status === 'invited').length;
  const totalEmails  = TEAM_MEMBERS.reduce((s, m) => s + m.emailsSent, 0);
  const totalAI      = TEAM_MEMBERS.reduce((s, m) => s + m.aiActionsTriggered, 0);

  return (
    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0 }}>

      {/* ── Top header ── */}
      <Box sx={{
        px: { xs: 2, sm: 3 }, py: 1.5, flexShrink: 0,
        borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
        background: isDark ? 'rgba(8,13,24,0.8)' : theme.palette.background.paper,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap',
        animation: 'fadeDown 0.3s ease-out',
        '@keyframes fadeDown': { from: { opacity: 0, transform: 'translateY(-6px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Typography sx={{ fontSize: { xs: '1.1rem', sm: '1.25rem' }, fontWeight: 800, letterSpacing: '-0.025em', color: 'text.primary', lineHeight: 1 }}>
                Team
              </Typography>
              <Box sx={{
                px: 0.65, py: 0.2, borderRadius: '6px',
                background: isDark ? 'rgba(129,140,248,0.15)' : alpha('#818cf8', 0.08),
                border: `1px solid ${alpha('#818cf8', 0.25)}`,
                display: 'flex', alignItems: 'center', gap: 0.35,
              }}>
                <ShieldRoundedIcon sx={{ fontSize: 9, color: '#818cf8' }} />
                <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: '#818cf8' }}>RBAC</Typography>
              </Box>
            </Box>
            <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', mt: 0.2 }}>
              Manage your team and permissions
            </Typography>
          </Box>

          {/* Inline stat pills */}
          <Box sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center', gap: 0.75 }}>
            {[
              { label: 'Members',  value: TEAM_MEMBERS.length, color: '#818cf8' },
              { label: 'Active',   value: totalActive,         color: '#34d399' },
              { label: 'Pending',  value: totalInvited,        color: '#60a5fa' },
              { label: 'Emails',   value: totalEmails,         color: '#fbbf24' },
              { label: 'AI Actions', value: totalAI,           color: '#c084fc' },
            ].map(s => (
              <Box key={s.label} sx={{
                display: 'flex', alignItems: 'center', gap: 0.5,
                px: 1, py: 0.45, borderRadius: '8px',
                background: isDark ? alpha(s.color, 0.1) : alpha(s.color, 0.07),
                border: `1px solid ${alpha(s.color, isDark ? 0.2 : 0.15)}`,
              }}>
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 800, color: s.color, lineHeight: 1 }}>
                  <CountUp target={s.value} />
                </Typography>
                <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>{s.label}</Typography>
              </Box>
            ))}
          </Box>
        </Box>

        {/* Actions */}
        <Box sx={{ display: 'flex', gap: 0.75 }}>
          <Button
            startIcon={<SettingsRoundedIcon sx={{ fontSize: '14px !important' }} />}
            sx={{
              fontWeight: 700, fontSize: '0.72rem', px: 1.5, py: 0.7, borderRadius: '9px',
              textTransform: 'none', flexShrink: 0,
              border: `1px solid ${isDark ? 'rgba(255,255,255,0.12)' : theme.palette.divider}`,
              color: 'text.primary', background: 'transparent',
              '&:hover': { background: isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.04) },
            }}
          >
            Roles
          </Button>
          <Button
            startIcon={<AddRoundedIcon sx={{ fontSize: '15px !important' }} />}
            onClick={() => setInviteOpen(true)}
            sx={{
              background: grad, color: '#fff', fontWeight: 700,
              fontSize: '0.75rem', px: 1.75, py: 0.75, borderRadius: '9px',
              textTransform: 'none', flexShrink: 0,
              boxShadow: isDark ? '0 4px 16px rgba(129,140,248,0.3)' : '0 4px 16px rgba(67,56,202,0.22)',
              transition: 'all 0.2s ease',
              '&:hover': { opacity: 0.88, transform: 'translateY(-1px)' },
              '&:active': { transform: 'scale(0.98)' },
            }}
          >
            Invite Member
          </Button>
        </Box>
      </Box>

      {/* ── Body ── */}
      <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>

        {/* Left panel — desktop only */}
        <Box sx={{ display: { xs: 'none', md: 'flex' }, flexDirection: 'column', overflow: 'hidden' }}>
          <LeftPanel
            members={TEAM_MEMBERS}
            activeFilter={activeFilter}
            onFilter={setActiveFilter}
            isDark={isDark}
            theme={theme}
          />
        </Box>

        {/* Right content */}
        <Box sx={{
          flex: 1, overflowY: 'auto', minWidth: 0,
          px: { xs: 2, sm: 2.5 }, py: 2,
          '&::-webkit-scrollbar': { width: 4 },
          '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
        }}>

          {/* Tab bar + search */}
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.75, gap: 1, flexWrap: 'wrap' }}>
            {/* Tabs */}
            <Box sx={{ display: 'flex', gap: 0.25, p: 0.35, borderRadius: '10px', background: isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04), border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}` }}>
              {([
                { id: 'members',  label: 'Members',  icon: GroupsRoundedIcon },
                { id: 'activity', label: 'Activity',  icon: BoltRoundedIcon },
              ] as const).map(({ id, label, icon: Icon }) => (
                <Box key={id} component="button" onClick={() => setActiveTab(id)} sx={{
                  display: 'flex', alignItems: 'center', gap: 0.5,
                  px: 1.1, py: 0.5, borderRadius: '8px', border: 'none', cursor: 'pointer',
                  background: activeTab === id ? isDark ? 'rgba(129,140,248,0.2)' : alpha('#818cf8', 0.12) : 'transparent',
                  color: activeTab === id ? (isDark ? '#818cf8' : theme.palette.primary.main) : theme.palette.text.secondary,
                  transition: 'all 0.15s ease',
                }}>
                  <Icon sx={{ fontSize: 13 }} />
                  <Typography sx={{ fontSize: '0.72rem', fontWeight: activeTab === id ? 700 : 500, color: 'inherit' }}>{label}</Typography>
                </Box>
              ))}
            </Box>

            {/* Search + filter */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Box sx={{
                display: 'flex', alignItems: 'center', gap: 0.75,
                px: 1.1, py: 0.6, borderRadius: '9px',
                background: isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04),
                border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider}`,
                flex: { xs: '1 1 auto', sm: '0 0 200px' },
              }}>
                <SearchRoundedIcon sx={{ fontSize: 13, color: 'text.disabled', flexShrink: 0 }} />
                <InputBase
                  placeholder="Search members..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  sx={{ fontSize: '0.73rem', color: 'text.primary', flex: 1, '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 } }}
                />
                {search && (
                  <IconButton size="small" onClick={() => setSearch('')} sx={{ p: 0.15, color: 'text.disabled' }}>
                    <CloseRoundedIcon sx={{ fontSize: 11 }} />
                  </IconButton>
                )}
              </Box>
            </Box>
          </Box>

          {/* Members tab */}
          {activeTab === 'members' && (
            <Box sx={{ pb: 4 }}>
              {filtered.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 10 }}>
                  <GroupsRoundedIcon sx={{ fontSize: 40, color: 'text.disabled', mb: 1.5 }} />
                  <Typography sx={{ fontSize: '0.88rem', color: 'text.secondary', mb: 0.5 }}>No members found</Typography>
                  <Typography sx={{ fontSize: '0.72rem', color: 'text.disabled', mb: 2 }}>
                    {search ? 'Try a different search term' : 'Invite your first team member'}
                  </Typography>
                  <Button onClick={() => setInviteOpen(true)} startIcon={<AddRoundedIcon />} sx={{
                    background: grad, color: '#fff', fontWeight: 700, fontSize: '0.75rem',
                    px: 2, py: 0.8, borderRadius: '9px', textTransform: 'none',
                  }}>Invite Member</Button>
                </Box>
              ) : (
                <Box sx={{
                  borderRadius: '14px', overflow: 'hidden',
                  border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
                  background: isDark ? 'rgba(255,255,255,0.02)' : theme.palette.background.paper,
                }}>
                  {/* Desktop table header */}
                  <Box sx={{
                    display: { xs: 'none', lg: 'grid' },
                    gridTemplateColumns: '1fr 130px 90px 90px 100px 80px',
                    alignItems: 'center', gap: 1.5, px: 1.75, py: 0.75,
                    background: isDark ? 'rgba(255,255,255,0.03)' : alpha(theme.palette.text.primary, 0.02),
                    borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
                  }}>
                    {['Member', 'Role', 'Status', 'Permissions', 'Last Active', 'Actions'].map(h => (
                      <Typography key={h} sx={{ fontSize: '0.58rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                        {h}
                      </Typography>
                    ))}
                  </Box>

                  {/* Desktop rows */}
                  <Box sx={{ display: { xs: 'none', lg: 'block' } }}>
                    {filtered.map((m, i) => (
                      <MemberRow
                        key={m.id} member={m} isDark={isDark} theme={theme} index={i}
                        onEdit={setEditMember} isCurrentUser={m.id === currentUserId}
                      />
                    ))}
                  </Box>

                  {/* Mobile cards */}
                  <Box sx={{ display: { xs: 'block', lg: 'none' } }}>
                    {filtered.map((m, i) => (
                      <MemberCard
                        key={m.id} member={m} isDark={isDark} theme={theme} index={i}
                        onEdit={setEditMember} isCurrentUser={m.id === currentUserId}
                      />
                    ))}
                  </Box>
                </Box>
              )}

              {/* Role legend */}
              <Box sx={{
                mt: 2, p: 1.5, borderRadius: '12px',
                border: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
                background: isDark ? 'rgba(255,255,255,0.015)' : alpha(theme.palette.text.primary, 0.01),
                display: 'flex', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap',
              }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
                  <ShieldRoundedIcon sx={{ fontSize: 12, color: 'text.disabled' }} />
                  <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Role Guide</Typography>
                </Box>
                {(['owner', 'admin', 'member'] as MemberRole[]).map(r => {
                  const cfg = ROLE_CONFIG[r];
                  return (
                    <Box key={r} sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.6 }}>
                      <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: cfg.color, mt: 0.35, flexShrink: 0 }} />
                      <Box>
                        <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: cfg.color }}>{cfg.label}</Typography>
                        <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled', lineHeight: 1.4 }}>{cfg.description}</Typography>
                      </Box>
                    </Box>
                  );
                })}
              </Box>
            </Box>
          )}

          {/* Activity tab */}
          {activeTab === 'activity' && (
            <Box sx={{ pb: 4 }}>
              <ActivityFeed isDark={isDark} theme={theme} />
            </Box>
          )}
        </Box>
      </Box>

      {/* Edit member panel */}
      {editMember && (
        <EditMemberPanel
          member={editMember} isDark={isDark} theme={theme}
          onClose={() => setEditMember(null)}
        />
      )}

      {/* Invite modal */}
      <InviteModal open={inviteOpen} onClose={() => setInviteOpen(false)} isDark={isDark} theme={theme} />
    </Box>
  );
}
