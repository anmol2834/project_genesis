'use client';

import { useState, useEffect, useRef } from 'react';
import {
  Box, Typography, useTheme, alpha, IconButton,
  Tooltip, Button, Modal, Switch, InputBase, type Theme,
} from '@mui/material';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import SyncRoundedIcon from '@mui/icons-material/SyncRounded';
import PauseCircleRoundedIcon from '@mui/icons-material/PauseCircleRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import LockRoundedIcon from '@mui/icons-material/LockRounded';
import ShieldRoundedIcon from '@mui/icons-material/ShieldRounded';
import DnsRoundedIcon from '@mui/icons-material/DnsRounded';
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded';
import VisibilityOffRoundedIcon from '@mui/icons-material/VisibilityOffRounded';
import { useAccounts } from '@/hooks/queries/useAccounts';
import { useConnectEmail } from '@/hooks/mutations/useEmailMutations';
import { useToggleAutomation, useSyncAccount, useDeleteAccount } from '@/hooks/mutations/useAccountMutations';
import type { EmailAccountFull } from '@/services/endpoints/email';
import { initiateOAuth } from '@/utils/oauth';

// ── Animated counter ──────────────────────────────────────────────────────────
function CountUp({ target, suffix = '' }: { target: number; suffix?: string }) {
  const [val, setVal] = useState(0);
  const frame = useRef<number | null>(null);
  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / 1100, 1);
      setVal(Math.round((1 - Math.pow(1 - p, 3)) * target));
      if (p < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => { if (frame.current) cancelAnimationFrame(frame.current); };
  }, [target]);
  return <>{val.toLocaleString()}{suffix}</>;
}

// ── Provider logo (inline SVG) ────────────────────────────────────────────────
function ProviderLogo({ provider, size = 20 }: { provider: string; size?: number }) {
  if (provider === 'gmail') return (
    <Box component="svg" viewBox="0 0 48 48" sx={{ width: size, height: size, flexShrink: 0 }}>
      <path fill="#EA4335" d="M6 40h6V22.5L4 16v20c0 2.2 1.8 4 4 4z" />
      <path fill="#34A853" d="M36 40h6c2.2 0 4-1.8 4-4V16l-8 6.5V40z" />
      <path fill="#FBBC05" d="M36 8H12L4 16l8 6.5 12-9.8 12 9.8L44 16 36 8z" />
      <path fill="#4285F4" d="M12 22.5V40h24V22.5L24 12.7 12 22.5z" />
    </Box>
  );
  if (provider === 'outlook') return (
    <Box component="svg" viewBox="0 0 48 48" sx={{ width: size, height: size, flexShrink: 0 }}>
      <rect x="2" y="8" width="28" height="32" rx="3" fill="#0078D4" />
      <rect x="18" y="14" width="28" height="22" rx="3" fill="#50E6FF" opacity="0.9" />
      <rect x="18" y="14" width="28" height="22" rx="3" fill="none" stroke="#0078D4" strokeWidth="1" />
      <ellipse cx="16" cy="24" rx="7" ry="8" fill="#fff" />
    </Box>
  );
  return (
    <Box sx={{ width: size, height: size, borderRadius: '50%', background: 'rgba(129,140,248,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
      <EmailRoundedIcon sx={{ fontSize: size * 0.6, color: '#818cf8' }} />
    </Box>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const isConnected = status === 'connected';
  const isSyncing   = status === 'syncing';
  const color = isConnected ? '#34d399' : isSyncing ? '#60a5fa' : '#fbbf24';
  const label = isConnected ? 'Connected' : isSyncing ? 'Syncing' : 'Paused';
  const Icon  = isConnected ? CheckCircleRoundedIcon : isSyncing ? SyncRoundedIcon : PauseCircleRoundedIcon;
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.45,
      px: 0.75, py: 0.25, borderRadius: '6px',
      background: `${color}1a`, border: `1px solid ${color}4d`,
    }}>
      <Icon sx={{
        fontSize: 10, color,
        animation: isSyncing ? 'spin 1.5s linear infinite' : 'none',
        '@keyframes spin': { from: { transform: 'rotate(0deg)' }, to: { transform: 'rotate(360deg)' } },
      }} />
      <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color, letterSpacing: '0.04em' }}>{label}</Typography>
    </Box>
  );
}

// ── Usage bar ─────────────────────────────────────────────────────────────────
function UsageBar({ used, limit, color, isDark }: { used: number; limit: number; color: string; isDark: boolean }) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const barColor = pct > 85 ? '#f87171' : pct > 60 ? '#fbbf24' : color;
  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.4 }}>
        <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>Daily usage</Typography>
        <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: barColor }}>{used}/{limit}</Typography>
      </Box>
      <Box sx={{ height: 3, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)', overflow: 'hidden' }}>
        <Box sx={{ height: '100%', borderRadius: 2, width: `${pct}%`, background: barColor, transition: 'width 0.8s ease' }} />
      </Box>
    </Box>
  );
}

// ── Summary stats ─────────────────────────────────────────────────────────────
function SummaryStats({ accounts, isDark, theme }: { accounts: EmailAccountFull[]; isDark: boolean; theme: Theme }) {
  const total     = accounts.length;
  const active    = accounts.filter(a => a.connection_status === 'connected').length;
  const healthy   = accounts.filter(a => a.connection_status === 'connected' || a.sync_status === 'syncing').length;
  const processed = accounts.reduce((s, a) => s + a.daily_sent_count, 0);

  const stats = [
    { label: 'Total Accounts',   value: total,     suffix: '',  color: '#818cf8', darkBg: 'rgba(129,140,248,0.12)', lightBg: 'rgba(129,140,248,0.07)', Icon: EmailRoundedIcon },
    { label: 'Active',           value: active,    suffix: '',  color: '#34d399', darkBg: 'rgba(52,211,153,0.12)',  lightBg: 'rgba(52,211,153,0.07)',  Icon: CheckCircleRoundedIcon },
    { label: 'Healthy Sync',     value: healthy,   suffix: '',  color: '#60a5fa', darkBg: 'rgba(96,165,250,0.12)',  lightBg: 'rgba(96,165,250,0.07)',  Icon: SyncRoundedIcon },
    { label: 'Emails Processed', value: processed, suffix: '',  color: '#c084fc', darkBg: 'rgba(192,132,252,0.12)', lightBg: 'rgba(192,132,252,0.07)', Icon: TrendingUpRoundedIcon },
  ];

  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', lg: 'repeat(4, 1fr)' }, gap: 1.5 }}>
      {stats.map((s, i) => (
        <Box key={s.label} sx={{
          p: { xs: 1.5, sm: 2 }, borderRadius: '14px',
          border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
          background: isDark ? s.darkBg : s.lightBg,
          position: 'relative', overflow: 'hidden',
          transition: 'transform 0.2s ease, box-shadow 0.2s ease',
          '&:hover': { transform: 'translateY(-2px)', boxShadow: isDark ? '0 12px 32px rgba(0,0,0,0.35)' : '0 12px 32px rgba(15,23,42,0.08)' },
          '&::before': { content: '""', position: 'absolute', top: 0, left: 0, right: 0, height: '2px', background: `linear-gradient(90deg, ${s.color}, ${alpha(s.color, 0.2)})` },
          animation: `cardIn 0.3s ease-out ${i * 0.06}s both`,
          '@keyframes cardIn': { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        }}>
          <Box sx={{ width: 32, height: 32, borderRadius: '9px', background: alpha(s.color, isDark ? 0.2 : 0.15), border: `1px solid ${alpha(s.color, 0.25)}`, display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 1.25 }}>
            <s.Icon sx={{ fontSize: 16, color: s.color }} />
          </Box>
          <Typography sx={{ fontSize: { xs: '1.4rem', sm: '1.6rem' }, fontWeight: 800, letterSpacing: '-0.04em', lineHeight: 1, color: 'text.primary' }}>
            <CountUp target={s.value} suffix={s.suffix} />
          </Typography>
          <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, mt: 0.4, color: 'text.secondary' }}>{s.label}</Typography>
        </Box>
      ))}
    </Box>
  );
}

// ── Account card ──────────────────────────────────────────────────────────────
function AccountCard({ account, isDark, theme, index, onToggle, onSync, onDelete }: {
  account: EmailAccountFull; isDark: boolean; theme: Theme; index: number;
  onToggle: (id: string, enabled: boolean) => void;
  onSync:   (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const statusColor = account.connection_status === 'connected' ? '#34d399'
    : account.connection_status === 'error' ? '#f87171' : '#fbbf24';

  const usagePct = account.daily_send_limit > 0
    ? Math.min((account.daily_sent_count / account.daily_send_limit) * 100, 100) : 0;
  const barColor = usagePct > 85 ? '#f87171' : usagePct > 60 ? '#fbbf24' : statusColor;

  const lastSync = account.last_synced_at
    ? new Date(account.last_synced_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : 'Never';

  return (
    <Box sx={{
      borderRadius: '14px',
      border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
      background: isDark ? 'linear-gradient(145deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02))' : theme.palette.background.paper,
      position: 'relative', overflow: 'hidden',
      transition: 'transform 0.2s ease, box-shadow 0.2s ease',
      '&:hover': {
        transform: 'translateY(-3px)',
        boxShadow: isDark
          ? `0 16px 40px rgba(0,0,0,0.4), 0 0 0 1px ${alpha(statusColor, 0.2)}`
          : `0 16px 40px rgba(15,23,42,0.1), 0 0 0 1px ${alpha(statusColor, 0.15)}`,
      },
      '&::before': {
        content: '""', position: 'absolute', top: 0, left: 0, right: 0, height: '2.5px',
        background: `linear-gradient(90deg, ${statusColor}, ${alpha(statusColor, 0.2)})`,
      },
      animation: `cardIn 0.3s ease-out ${index * 0.07}s both`,
      '@keyframes cardIn': { from: { opacity: 0, transform: 'translateY(10px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
    }}>
      <Box sx={{ p: { xs: 1.75, sm: 2 } }}>
        {/* Top row */}
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0, flex: 1 }}>
            <Box sx={{ width: 44, height: 44, borderRadius: '12px', flexShrink: 0, background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.04), border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <ProviderLogo provider={account.provider} size={24} />
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontSize: '0.88rem', fontWeight: 700, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {account.email_address}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.3 }}>
                <StatusBadge status={account.connection_status} />
                <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>Synced {lastSync}</Typography>
              </Box>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 0.25, flexShrink: 0, ml: 1 }}>
            <Tooltip title="Refresh sync" placement="top">
              <IconButton size="small" onClick={() => onSync(account.id)} sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary', '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) } }}>
                <RefreshRoundedIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
            <Tooltip title="Remove account" placement="top">
              <IconButton size="small" onClick={() => onDelete(account.id)} sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary', '&:hover': { background: 'rgba(239,68,68,0.1)', color: '#ef4444' } }}>
                <DeleteOutlineRoundedIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Stats row */}
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1, mb: 1.5 }}>
          {[
            { label: 'Daily Limit', value: account.daily_send_limit, color: '#818cf8' },
            { label: 'Sent Today',  value: account.daily_sent_count,  color: '#22d3ee' },
            { label: 'Warmup',      value: account.warmup_enabled ? 1 : 0, color: '#34d399', suffix: account.warmup_enabled ? ' ON' : ' OFF' },
          ].map(({ label, value, color, suffix = '' }) => (
            <Box key={label} sx={{ p: 1, borderRadius: '10px', textAlign: 'center', background: isDark ? 'rgba(255,255,255,0.04)' : alpha(theme.palette.text.primary, 0.03), border: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}` }}>
              <Typography sx={{ fontSize: { xs: '0.9rem', sm: '1rem' }, fontWeight: 800, color: 'text.primary', lineHeight: 1, letterSpacing: '-0.02em' }}>
                {suffix ? <span style={{ color }}>{value > 0 ? 'ON' : 'OFF'}</span> : <CountUp target={value} />}
              </Typography>
              <Typography sx={{ fontSize: '0.55rem', color: 'text.disabled', mt: 0.25, fontWeight: 500 }}>{label}</Typography>
            </Box>
          ))}
        </Box>

        {/* Daily usage bar */}
        <Box sx={{ mb: 1.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.4 }}>
            <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>Daily usage</Typography>
            <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: barColor }}>{account.daily_sent_count}/{account.daily_send_limit}</Typography>
          </Box>
          <Box sx={{ height: 3, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)', overflow: 'hidden' }}>
            <Box sx={{ height: '100%', borderRadius: 2, width: `${usagePct}%`, background: barColor, transition: 'width 0.8s ease' }} />
          </Box>
        </Box>

        {/* Automation toggle */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.25 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            <Switch size="small" checked={account.automation_enabled}
              onChange={() => onToggle(account.id, !account.automation_enabled)}
              sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#34d399' }, '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { backgroundColor: '#34d399' } }}
            />
            <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, color: account.automation_enabled ? '#34d399' : 'text.disabled' }}>
              Automation {account.automation_enabled ? 'ON' : 'OFF'}
            </Typography>
          </Box>
          <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>
            {account.is_primary ? '★ Primary' : account.display_name ?? account.provider}
          </Typography>
        </Box>

        {/* Error message if any */}
        {account.last_error_message && (
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.75, px: 1, py: 0.75, borderRadius: '9px', background: isDark ? alpha('#f87171', 0.07) : alpha('#f87171', 0.05), border: `1px solid ${alpha('#f87171', isDark ? 0.18 : 0.15)}` }}>
            <WarningAmberRoundedIcon sx={{ fontSize: 12, color: '#f87171', mt: 0.1, flexShrink: 0 }} />
            <Typography sx={{ fontSize: '0.67rem', color: '#f87171', lineHeight: 1.45, fontWeight: 500 }}>
              {account.last_error_message}
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}

// ── Connect modal ─────────────────────────────────────────────────────────────
function ConnectModal({ open, onClose, isDark, theme }: {
  open: boolean; onClose: () => void; isDark: boolean; theme: Theme;
}) {
  const [tab, setTab] = useState<'oauth' | 'smtp'>('oauth');
  const [showPass, setShowPass] = useState(false);
  const [smtp, setSmtp] = useState({ name: '', email: '', host: '', port: '587', user: '', pass: '', encryption: 'TLS' });

  const { mutate: connectEmail, isPending, isSuccess, error, reset } = useConnectEmail();

  const handleOAuth = async (provider: 'gmail' | 'outlook') => {
    try {
      await initiateOAuth(provider);
    } catch (err) {
      console.error('OAuth initiation failed:', err);
    }
  };

  const handleSmtp = () => {
    connectEmail({
      provider: 'smtp',
      connection_type: 'manual',
      email: smtp.email,
      credentials: {
        smtp_host: smtp.host,
        smtp_port: parseInt(smtp.port, 10),
        username: smtp.user,
        password: smtp.pass,
        smtp_use_tls: smtp.encryption === 'TLS',
      },
    });
  };

  const handleClose = () => { reset(); onClose(); };

  const oauthProviders = [
    { id: 'google' as const,    providerKey: 'gmail' as const,    name: 'Google Gmail',       desc: 'Connect via secure OAuth 2.0', color: '#EA4335', bg: isDark ? 'rgba(234,67,53,0.1)' : 'rgba(234,67,53,0.06)', border: isDark ? 'rgba(234,67,53,0.25)' : 'rgba(234,67,53,0.2)' },
    { id: 'microsoft' as const, providerKey: 'outlook' as const,  name: 'Microsoft Outlook',  desc: 'Connect via Microsoft OAuth',  color: '#0078D4', bg: isDark ? 'rgba(0,120,212,0.1)' : 'rgba(0,120,212,0.06)', border: isDark ? 'rgba(0,120,212,0.25)' : 'rgba(0,120,212,0.2)' },
  ];

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
    <Modal open={open} onClose={handleClose} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
      <Box sx={{
        width: '100%', maxWidth: 440,
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
          px: 2.5, pt: 2.5, pb: 2,
          borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
        }}>
          <Box>
            <Typography sx={{ fontSize: '1rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em' }}>
              Connect Email Account
            </Typography>
            <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', mt: 0.3 }}>
              Choose your email provider to get started
            </Typography>
          </Box>
          <IconButton size="small" onClick={handleClose} sx={{
            width: 28, height: 28, borderRadius: '7px', color: 'text.secondary',
            '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) },
          }}>
            <CloseRoundedIcon sx={{ fontSize: 15 }} />
          </IconButton>
        </Box>

        {/* Tabs */}
        <Box sx={{ display: 'flex', gap: 0.5, px: 2, pt: 1.75, pb: 0.25 }}>
          {([
            { id: 'oauth', label: 'OAuth Providers' },
            { id: 'smtp',  label: 'Custom SMTP' },
          ] as const).map((t) => (
            <Box key={t.id} component="button" onClick={() => setTab(t.id)} sx={{
              px: 1.25, py: 0.55, borderRadius: '8px', border: 'none', cursor: 'pointer',
              fontSize: '0.72rem', fontWeight: tab === t.id ? 700 : 500,
              background: tab === t.id
                ? isDark ? 'rgba(129,140,248,0.18)' : alpha(theme.palette.primary.main, 0.1)
                : 'transparent',
              color: tab === t.id
                ? isDark ? '#818cf8' : theme.palette.primary.main
                : theme.palette.text.secondary,
              transition: 'all 0.15s ease',
              display: 'flex', alignItems: 'center', gap: 0.5,
            }}>
              {t.id === 'smtp' && <DnsRoundedIcon sx={{ fontSize: 13 }} />}
              {t.label}
            </Box>
          ))}
        </Box>

        {/* OAuth tab */}
        {tab === 'oauth' && (
          <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
            {isSuccess && (
              <Box sx={{ px: 1.5, py: 1, borderRadius: '9px', background: 'rgba(52,211,153,0.1)', border: '1px solid rgba(52,211,153,0.25)', display: 'flex', alignItems: 'center', gap: 0.75 }}>
                <CheckCircleRoundedIcon sx={{ fontSize: 14, color: '#34d399' }} />
                <Typography sx={{ fontSize: '0.72rem', color: '#34d399', fontWeight: 600 }}>Account connected successfully!</Typography>
              </Box>
            )}
            {error && (
              <Box sx={{ px: 1.5, py: 1, borderRadius: '9px', background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.25)' }}>
                <Typography sx={{ fontSize: '0.72rem', color: '#f87171' }}>{(error as { message?: string })?.message ?? 'Connection failed. Please try again.'}</Typography>
              </Box>
            )}
            {oauthProviders.map((p) => (
              <Box key={p.id} component="button"
                onClick={() => !isPending && !isSuccess && handleOAuth(p.providerKey)}
                disabled={isPending || isSuccess}
                sx={{
                  display: 'flex', alignItems: 'center', gap: 1.5,
                  p: 1.5, borderRadius: '12px', border: `1.5px solid ${p.border}`,
                  background: p.bg, cursor: isPending || isSuccess ? 'not-allowed' : 'pointer',
                  textAlign: 'left', width: '100%', opacity: isPending || isSuccess ? 0.7 : 1,
                  transition: 'all 0.18s ease',
                  '&:hover': !isPending && !isSuccess ? { transform: 'translateY(-1px)', boxShadow: isDark ? '0 8px 24px rgba(0,0,0,0.3)' : '0 8px 24px rgba(15,23,42,0.08)', borderColor: p.color } : {},
                }}>
                <Box sx={{ width: 44, height: 44, borderRadius: '11px', flexShrink: 0, background: isDark ? 'rgba(255,255,255,0.07)' : '#fff', border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(15,23,42,0.08)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
                  <ProviderLogo provider={p.id === 'google' ? 'gmail' : 'outlook'} size={24} />
                </Box>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography sx={{ fontSize: '0.88rem', fontWeight: 700, color: 'text.primary' }}>{p.name}</Typography>
                  <Typography sx={{ fontSize: '0.67rem', color: 'text.secondary', mt: 0.15 }}>{p.desc}</Typography>
                </Box>
                <Box sx={{ px: 1.25, py: 0.5, borderRadius: '8px', flexShrink: 0, background: p.color, color: '#fff', fontSize: '0.68rem', fontWeight: 700 }}>
                  {isPending ? 'Connecting…' : isSuccess ? 'Connected' : 'Connect'}
                </Box>
              </Box>
            ))}
          </Box>
        )}

        {/* SMTP tab */}
        {tab === 'smtp' && (
          <Box sx={{ px: 2, pt: 1.5, pb: 2, display: 'flex', flexDirection: 'column', gap: 1.1 }}>
            {/* Account name + email */}
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Account Name</Typography>
                <InputBase value={smtp.name} onChange={(e) => setSmtp(s => ({ ...s, name: e.target.value }))}
                  placeholder="e.g. Work Email" sx={inputSx} fullWidth />
              </Box>
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>From Email</Typography>
                <InputBase value={smtp.email} onChange={(e) => setSmtp(s => ({ ...s, email: e.target.value }))}
                  placeholder="you@domain.com" sx={inputSx} fullWidth />
              </Box>
            </Box>

            {/* SMTP host + port */}
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 80px', gap: 1 }}>
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>SMTP Host</Typography>
                <InputBase value={smtp.host} onChange={(e) => setSmtp(s => ({ ...s, host: e.target.value }))}
                  placeholder="smtp.domain.com" sx={inputSx} fullWidth />
              </Box>
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Port</Typography>
                <InputBase value={smtp.port} onChange={(e) => setSmtp(s => ({ ...s, port: e.target.value }))}
                  placeholder="587" sx={inputSx} fullWidth />
              </Box>
            </Box>

            {/* Username */}
            <Box>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Username</Typography>
              <InputBase value={smtp.user} onChange={(e) => setSmtp(s => ({ ...s, user: e.target.value }))}
                placeholder="SMTP username" sx={inputSx} fullWidth />
            </Box>

            {/* Password */}
            <Box>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Password / App Password</Typography>
              <Box sx={{ ...inputSx, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <InputBase
                  type={showPass ? 'text' : 'password'}
                  value={smtp.pass}
                  onChange={(e) => setSmtp(s => ({ ...s, pass: e.target.value }))}
                  placeholder="••••••••••••"
                  sx={{ flex: 1, fontSize: '0.8rem', color: 'text.primary', '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 } }}
                />
                <IconButton size="small" onClick={() => setShowPass(v => !v)}
                  sx={{ p: 0.25, color: 'text.disabled', '&:hover': { color: 'text.secondary' } }}>
                  {showPass
                    ? <VisibilityOffRoundedIcon sx={{ fontSize: 15 }} />
                    : <VisibilityRoundedIcon sx={{ fontSize: 15 }} />}
                </IconButton>
              </Box>
            </Box>

            {/* Encryption */}
            <Box>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Encryption</Typography>
              <Box sx={{ display: 'flex', gap: 0.75 }}>
                {['TLS', 'SSL', 'None'].map((enc) => (
                  <Box key={enc} component="button" onClick={() => setSmtp(s => ({ ...s, encryption: enc }))} sx={{
                    px: 1.25, py: 0.5, borderRadius: '7px', border: 'none', cursor: 'pointer',
                    fontSize: '0.7rem', fontWeight: 600,
                    background: smtp.encryption === enc
                      ? isDark ? 'rgba(129,140,248,0.2)' : alpha(theme.palette.primary.main, 0.1)
                      : isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04),
                    color: smtp.encryption === enc
                      ? isDark ? '#818cf8' : theme.palette.primary.main
                      : theme.palette.text.secondary,
                    border: `1px solid ${smtp.encryption === enc ? (isDark ? 'rgba(129,140,248,0.3)' : alpha(theme.palette.primary.main, 0.25)) : (isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider)}`,
                    transition: 'all 0.15s ease',
                  }}>
                    {enc}
                  </Box>
                ))}
              </Box>
            </Box>

            {/* Connect button */}
            <Box component="button" onClick={handleSmtp} disabled={isPending} sx={{
              mt: 0.5, width: '100%', border: 'none', cursor: isPending ? 'not-allowed' : 'pointer',
              py: 0.9, borderRadius: '10px', opacity: isPending ? 0.7 : 1,
              background: isDark ? 'linear-gradient(135deg, #4f46e5, #818cf8)' : 'linear-gradient(135deg, #4338ca, #6366f1)',
              color: '#fff', fontSize: '0.78rem', fontWeight: 700,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.75,
              transition: 'opacity 0.15s ease, transform 0.15s ease',
              '&:hover': { opacity: isPending ? 0.7 : 0.88, transform: isPending ? 'none' : 'translateY(-1px)' },
            }}>
              <DnsRoundedIcon sx={{ fontSize: 15 }} />
              {isPending ? 'Connecting…' : 'Connect via SMTP'}
            </Box>
          </Box>
        )}

        {/* Trust indicators — shown on both tabs */}
        <Box sx={{
          mx: 2, mb: 2, px: 1.5, py: 1.1, borderRadius: '10px',
          background: isDark ? 'rgba(52,211,153,0.07)' : 'rgba(52,211,153,0.05)',
          border: `1px solid ${isDark ? 'rgba(52,211,153,0.18)' : 'rgba(52,211,153,0.15)'}`,
          display: 'flex', flexDirection: 'column', gap: 0.5,
        }}>
          {[
            { Icon: LockRoundedIcon, text: 'Credentials are encrypted and stored securely' },
            { Icon: ShieldRoundedIcon, text: 'Read/send permissions only — no data misuse' },
          ].map(({ Icon, text }) => (
            <Box key={text} sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Icon sx={{ fontSize: 12, color: '#34d399', flexShrink: 0 }} />
              <Typography sx={{ fontSize: '0.65rem', color: isDark ? alpha('#34d399', 0.85) : '#059669', fontWeight: 500 }}>
                {text}
              </Typography>
            </Box>
          ))}
        </Box>
      </Box>
    </Modal>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────
function EmptyState({ isDark, onConnect }: { isDark: boolean; onConnect: () => void }) {
  return (
    <Box sx={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', py: 10, gap: 2,
      animation: 'fadeIn 0.4s ease-out',
      '@keyframes fadeIn': { from: { opacity: 0 }, to: { opacity: 1 } },
    }}>
      <Box sx={{
        width: 80, height: 80, borderRadius: '22px',
        background: isDark ? 'rgba(129,140,248,0.12)' : 'rgba(67,56,202,0.07)',
        border: `1px solid ${isDark ? 'rgba(129,140,248,0.22)' : 'rgba(67,56,202,0.15)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        animation: 'float 3s ease-in-out infinite',
        '@keyframes float': {
          '0%,100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-6px)' },
        },
      }}>
        <EmailRoundedIcon sx={{ fontSize: 36, color: isDark ? '#818cf8' : '#4338ca' }} />
      </Box>
      <Box sx={{ textAlign: 'center' }}>
        <Typography sx={{ fontSize: '1.05rem', fontWeight: 800, color: 'text.primary', mb: 0.5, letterSpacing: '-0.02em' }}>
          No email accounts connected
        </Typography>
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', maxWidth: 300 }}>
          Connect your first account to start automating outreach and tracking replies.
        </Typography>
      </Box>
      <Button
        startIcon={<AddRoundedIcon />}
        onClick={onConnect}
        sx={{
          background: 'linear-gradient(135deg, #4f46e5, #818cf8)',
          color: '#fff', fontWeight: 700,
          fontSize: '0.78rem', px: 2.5, py: 0.9, borderRadius: '10px',
          textTransform: 'none',
          boxShadow: '0 4px 20px rgba(99,102,241,0.35)',
          '&:hover': { opacity: 0.88, transform: 'translateY(-1px)' },
        }}
      >
        Connect your first account
      </Button>
    </Box>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function EmailAccountsPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | string>('all');
  const [modalOpen, setModalOpen] = useState(false);

  // ── Real data via React Query ──
  const { data: accountsData, isLoading, isError } = useAccounts();
  const { mutate: toggleAutomation } = useToggleAutomation();
  const { mutate: syncAccount }      = useSyncAccount();
  const { mutate: deleteAccount }    = useDeleteAccount();

  const allAccounts = accountsData?.all ?? [];

  const filtered = allAccounts.filter((a) => {
    if (statusFilter !== 'all' && a.connection_status !== statusFilter) return false;
    if (search && !a.email_address.toLowerCase().includes(search.toLowerCase()) &&
        !(a.display_name ?? '').toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const STATUS_FILTERS = [
    { id: 'all',          label: 'All' },
    { id: 'connected',    label: 'Connected' },
    { id: 'syncing',      label: 'Syncing' },
    { id: 'disconnected', label: 'Paused' },
  ];

  return (
    <Box sx={{
      flex: 1, overflowY: 'auto',
      px: { xs: 2, sm: 3 }, py: { xs: 2, sm: 2.5 },
      '&::-webkit-scrollbar': { width: 4 },
      '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
    }}>
      <Box sx={{ maxWidth: 1200, mx: 'auto', display: 'flex', flexDirection: 'column', gap: 2.5, pb: 4 }}>

        {/* ── Header ── */}
        <Box sx={{
          display: 'flex', alignItems: { xs: 'flex-start', sm: 'center' },
          justifyContent: 'space-between', flexWrap: 'wrap', gap: 1.5,
          animation: 'fadeDown 0.3s ease-out',
          '@keyframes fadeDown': { from: { opacity: 0, transform: 'translateY(-8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        }}>
          <Box>
            <Typography sx={{ fontSize: { xs: '1.25rem', sm: '1.45rem' }, fontWeight: 800, letterSpacing: '-0.025em', color: 'text.primary', lineHeight: 1.2 }}>
              Email Accounts
            </Typography>
            <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mt: 0.3 }}>
              Manage connected accounts, sync status, and automation settings
            </Typography>
          </Box>
          <Button
            startIcon={<AddRoundedIcon sx={{ fontSize: '16px !important' }} />}
            onClick={() => setModalOpen(true)}
            sx={{
              background: isDark
                ? 'linear-gradient(135deg, #4f46e5, #818cf8)'
                : 'linear-gradient(135deg, #4338ca, #6366f1)',
              color: '#fff', fontWeight: 700,
              fontSize: '0.78rem', px: 2, py: 0.85, borderRadius: '10px',
              textTransform: 'none', flexShrink: 0,
              boxShadow: isDark ? '0 4px 20px rgba(129,140,248,0.3)' : '0 4px 20px rgba(67,56,202,0.25)',
              transition: 'all 0.2s ease',
              '&:hover': { opacity: 0.88, transform: 'translateY(-1px)', boxShadow: isDark ? '0 8px 28px rgba(129,140,248,0.4)' : '0 8px 28px rgba(67,56,202,0.35)' },
              '&:active': { transform: 'scale(0.98)' },
            }}
          >
            Connect Account
          </Button>
        </Box>

        {/* ── Summary stats ── */}
        <SummaryStats accounts={allAccounts} isDark={isDark} theme={theme} />

        {/* ── Search + filter ── */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
          <Box sx={{
            display: 'flex', alignItems: 'center', gap: 1,
            px: 1.25, py: 0.75, borderRadius: '10px',
            flex: { xs: '1 1 100%', sm: '0 0 240px' },
            background: isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04),
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider}`,
          }}>
            <EmailRoundedIcon sx={{ fontSize: 15, color: 'text.disabled', flexShrink: 0 }} />
            <InputBase
              placeholder="Search accounts..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              sx={{
                fontSize: '0.78rem', color: 'text.primary', flex: 1,
                '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 },
              }}
            />
          </Box>

          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
            {STATUS_FILTERS.map((f) => {
              const isActive = statusFilter === f.id;
              const count = f.id === 'all' ? allAccounts.length : allAccounts.filter(a => a.connection_status === f.id).length;
              return (
                <Box key={f.id} component="button" onClick={() => setStatusFilter(f.id)} sx={{
                  px: 1.1, py: 0.45, borderRadius: '8px', border: 'none', cursor: 'pointer',
                  fontSize: '0.7rem', fontWeight: isActive ? 700 : 500,
                  display: 'flex', alignItems: 'center', gap: 0.5,
                  background: isActive
                    ? isDark ? 'rgba(129,140,248,0.2)' : alpha(theme.palette.primary.main, 0.1)
                    : 'transparent',
                  color: isActive
                    ? isDark ? '#818cf8' : theme.palette.primary.main
                    : theme.palette.text.secondary,
                  transition: 'all 0.15s ease',
                  '&:hover': { background: isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.05) },
                }}>
                  {f.label}
                  <Box sx={{
                    minWidth: 16, height: 16, borderRadius: '5px', px: 0.4,
                    background: isActive
                      ? isDark ? 'rgba(129,140,248,0.3)' : alpha(theme.palette.primary.main, 0.15)
                      : isDark ? 'rgba(255,255,255,0.08)' : alpha(theme.palette.text.primary, 0.07),
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: isActive ? (isDark ? '#818cf8' : theme.palette.primary.main) : 'text.disabled', lineHeight: 1 }}>
                      {count}
                    </Typography>
                  </Box>
                </Box>
              );
            })}
          </Box>
        </Box>

        {/* ── Account grid or empty/loading/error state ── */}
        {isLoading ? (
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', xl: 'repeat(3, 1fr)' }, gap: 2 }}>
            {[1, 2, 3].map(i => (
              <Box key={i} sx={{ borderRadius: '14px', height: 260, background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)', border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`, animation: 'pulse 1.5s ease-in-out infinite', '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.5 } } }} />
            ))}
          </Box>
        ) : isError ? (
          <Box sx={{ textAlign: 'center', py: 8 }}>
            <WarningAmberRoundedIcon sx={{ fontSize: 36, color: '#f87171', mb: 1 }} />
            <Typography sx={{ fontSize: '0.88rem', color: 'text.secondary' }}>Failed to load accounts. Please refresh.</Typography>
          </Box>
        ) : filtered.length === 0 && search === '' && statusFilter === 'all' ? (
          <EmptyState isDark={isDark} onConnect={() => setModalOpen(true)} />
        ) : filtered.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 8 }}>
            <Typography sx={{ fontSize: '0.88rem', color: 'text.secondary' }}>No accounts match your filter.</Typography>
          </Box>
        ) : (
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', xl: 'repeat(3, 1fr)' }, gap: 2 }}>
            {filtered.map((account, i) => (
              <AccountCard
                key={account.id}
                account={account}
                isDark={isDark}
                theme={theme}
                index={i}
                onToggle={(id, enabled) => toggleAutomation({ id, enabled })}
                onSync={syncAccount}
                onDelete={deleteAccount}
              />
            ))}
          </Box>
        )}
      </Box>

      {/* ── Connect modal ── */}
      <ConnectModal open={modalOpen} onClose={() => setModalOpen(false)} isDark={isDark} theme={theme} />
    </Box>
  );
}
