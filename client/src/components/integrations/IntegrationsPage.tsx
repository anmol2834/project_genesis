'use client';

import { useState, useMemo, useRef, useEffect } from 'react';
import { Box, Typography, useTheme, alpha, InputBase, Modal, IconButton, Switch, type Theme } from '@mui/material';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import SyncRoundedIcon from '@mui/icons-material/SyncRounded';
import LinkOffRoundedIcon from '@mui/icons-material/LinkOffRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import LockRoundedIcon from '@mui/icons-material/LockRounded';
import VerifiedRoundedIcon from '@mui/icons-material/VerifiedRounded';
import TuneRoundedIcon from '@mui/icons-material/TuneRounded';
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded';
import FiberManualRecordRoundedIcon from '@mui/icons-material/FiberManualRecordRounded';
import ExtensionRoundedIcon from '@mui/icons-material/ExtensionRounded';
import ChevronRightRoundedIcon from '@mui/icons-material/ChevronRightRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded';
import DnsRoundedIcon from '@mui/icons-material/DnsRounded';
import ShieldRoundedIcon from '@mui/icons-material/ShieldRounded';
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded';
import VisibilityOffRoundedIcon from '@mui/icons-material/VisibilityOffRounded';
import UploadFileRoundedIcon from '@mui/icons-material/UploadFileRounded';
import {
  INTEGRATIONS, CATEGORIES, CONNECT_STEPS,
  type Integration, type CategoryId,
} from './integrationsData';
import CSVImportModal from '../shared/CSVImportModal';

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

// ── Status dot ────────────────────────────────────────────────────────────────
function StatusDot({ status, isDark }: { status: Integration['status']; isDark: boolean }) {
  const map = {
    connected:    { color: '#34d399', label: 'Connected', pulse: true },
    disconnected: { color: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.18)', label: 'Not connected', pulse: false },
    error:        { color: '#f87171', label: 'Error', pulse: true },
    syncing:      { color: '#fbbf24', label: 'Syncing', pulse: true },
  };
  const s = map[status];
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
      <Box sx={{
        width: 6, height: 6, borderRadius: '50%', background: s.color, flexShrink: 0,
        boxShadow: s.pulse ? `0 0 6px ${alpha(s.color, 0.7)}` : 'none',
        animation: s.pulse ? 'statusPulse 2.5s ease-in-out infinite' : 'none',
        '@keyframes statusPulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.4 } },
      }} />
      <Typography sx={{ fontSize: '0.62rem', fontWeight: 600, color: s.color }}>{s.label}</Typography>
    </Box>
  );
}

// ── Integration logo placeholder ──────────────────────────────────────────────
function IntegrationLogo({ integration, size = 40 }: { integration: Integration; size?: number }) {
  const initials = integration.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  return (
    <Box sx={{
      width: size, height: size, borderRadius: `${size * 0.25}px`, flexShrink: 0,
      background: integration.bgColor,
      border: `1.5px solid ${alpha(integration.color, 0.2)}`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      boxShadow: `0 2px 8px ${alpha(integration.color, 0.15)}`,
    }}>
      <Typography sx={{ fontSize: `${size * 0.3}px`, fontWeight: 900, color: integration.color, lineHeight: 1, letterSpacing: '-0.03em' }}>
        {initials}
      </Typography>
    </Box>
  );
}

// ── Compact action button ─────────────────────────────────────────────────────
function Btn({
  label, color = '#818cf8', onClick, icon: Icon, danger = false, isDark, size = 'sm', fullWidth = false,
}: {
  label: string; color?: string; onClick?: () => void; icon?: React.ElementType;
  danger?: boolean; isDark: boolean; theme: Theme; size?: 'sm' | 'xs' | 'md'; fullWidth?: boolean;
}) {
  const c = danger ? '#f87171' : color;
  const px = size === 'xs' ? 0.9 : size === 'md' ? 1.75 : 1.25;
  const py = size === 'xs' ? 0.35 : size === 'md' ? 0.75 : 0.55;
  const fs = size === 'xs' ? '0.65rem' : size === 'md' ? '0.78rem' : '0.72rem';
  return (
    <Box component="button" onClick={onClick} sx={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 0.5,
      px, py, borderRadius: '9px', width: fullWidth ? '100%' : 'auto',
      border: `1px solid ${alpha(c, isDark ? 0.3 : 0.22)}`,
      background: alpha(c, isDark ? 0.1 : 0.07),
      color: c, fontSize: fs, fontWeight: 600, cursor: 'pointer',
      transition: 'all 0.15s ease',
      '&:hover': {
        background: alpha(c, isDark ? 0.2 : 0.14),
        borderColor: alpha(c, 0.5),
        boxShadow: `0 0 12px ${alpha(c, 0.25)}`,
        transform: 'translateY(-1px)',
      },
    }}>
      {Icon && <Icon sx={{ fontSize: size === 'xs' ? 11 : size === 'md' ? 15 : 13 }} />}
      {label}
    </Box>
  );
}

// ── Glow chip ─────────────────────────────────────────────────────────────────
function GlowChip({ label, color, isDark }: { label: string; color: string; isDark: boolean }) {
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.35,
      px: 0.65, py: 0.15, borderRadius: '5px',
      background: alpha(color, isDark ? 0.15 : 0.1),
      border: `1px solid ${alpha(color, isDark ? 0.3 : 0.2)}`,
      boxShadow: `0 0 6px ${alpha(color, 0.18)}`,
    }}>
      <FiberManualRecordRoundedIcon sx={{ fontSize: 5, color }} />
      <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color, lineHeight: 1 }}>{label}</Typography>
    </Box>
  );
}

// ── Connect modal (step-by-step) ──────────────────────────────────────────────
function ConnectModal({
  integration, open, onClose, isDark, theme,
}: {
  integration: Integration | null; open: boolean; onClose: () => void;
  isDark: boolean; theme: Theme;
}) {
  const [step, setStep] = useState(0);

  if (!integration) return null;

  const isLast = step === CONNECT_STEPS.length - 1;

  const handleClose = () => {
    setStep(0);
    onClose();
  };

  return (
    <Modal open={open} onClose={handleClose}>
      <Box sx={{
        position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        width: { xs: '92vw', sm: 480 }, borderRadius: '20px', outline: 'none',
        background: isDark
          ? 'linear-gradient(145deg, #1e293b 0%, #0f172a 100%)'
          : 'linear-gradient(145deg, #ffffff 0%, #f8fafc 100%)',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'}`,
        boxShadow: `0 32px 80px ${alpha('#000', isDark ? 0.6 : 0.2)}`,
        overflow: 'hidden',
      }}>
        {/* Header */}
        <Box sx={{
          px: 2.5, pt: 2.5, pb: 2,
          borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)'}`,
          display: 'flex', alignItems: 'center', gap: 1.5,
        }}>
          <IntegrationLogo integration={integration} size={44} />
          <Box sx={{ flex: 1 }}>
            <Typography sx={{ fontSize: '0.95rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em' }}>
              Connect {integration.name}
            </Typography>
            <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mt: 0.1 }}>{integration.description}</Typography>
          </Box>
          <IconButton size="small" onClick={handleClose} sx={{ color: 'text.disabled', p: 0.5 }}>
            <CloseRoundedIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Box>

        {/* Step progress */}
        <Box sx={{ px: 2.5, pt: 1.75, pb: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0 }}>
            {CONNECT_STEPS.map((s, i) => (
              <Box key={s.id} sx={{ display: 'flex', alignItems: 'center', flex: i < CONNECT_STEPS.length - 1 ? 1 : 'none' }}>
                <Box sx={{
                  width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: i < step
                    ? '#34d399'
                    : i === step
                      ? alpha(integration.color, isDark ? 0.25 : 0.15)
                      : isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)',
                  border: `1.5px solid ${i <= step ? (i < step ? '#34d399' : integration.color) : isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`,
                  transition: 'all 0.25s ease',
                  boxShadow: i === step ? `0 0 12px ${alpha(integration.color, 0.4)}` : 'none',
                }}>
                  {i < step
                    ? <CheckRoundedIcon sx={{ fontSize: 13, color: '#fff' }} />
                    : <Typography sx={{ fontSize: '0.65rem', fontWeight: 800, color: i === step ? integration.color : 'text.disabled' }}>{s.id}</Typography>
                  }
                </Box>
                {i < CONNECT_STEPS.length - 1 && (
                  <Box sx={{ flex: 1, height: 1.5, mx: 0.5, borderRadius: 1, background: i < step ? '#34d399' : isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)', transition: 'background 0.3s ease' }} />
                )}
              </Box>
            ))}
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.75, px: 0.25 }}>
            {CONNECT_STEPS.map((s, i) => (
              <Typography key={s.id} sx={{ fontSize: '0.58rem', fontWeight: i === step ? 700 : 400, color: i === step ? integration.color : 'text.disabled', transition: 'color 0.2s' }}>
                {s.label}
              </Typography>
            ))}
          </Box>
        </Box>

        {/* Step content */}
        <Box sx={{ px: 2.5, py: 2, minHeight: 180 }}>
          {step === 0 && (
            <Box>
              <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary', mb: 1 }}>
                What {integration.name} does
              </Typography>
              <Typography sx={{ fontSize: '0.74rem', color: 'text.secondary', lineHeight: 1.7, mb: 1.5 }}>
                {integration.description} This integration enables real-time data sync, automated lead ingestion, and workflow triggers directly inside Proxipilot.
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.6 }}>
                {['Automatic lead sync', 'Real-time event triggers', 'Bidirectional data flow'].map(f => (
                  <Box key={f} sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                    <CheckRoundedIcon sx={{ fontSize: 13, color: '#34d399' }} />
                    <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{f}</Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          )}
          {step === 1 && (
            <Box>
              <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary', mb: 1 }}>
                Permissions required
              </Typography>
              {[
                { label: 'Read contacts & leads', icon: PeopleRoundedIcon, color: '#818cf8' },
                { label: 'Send emails on your behalf', icon: EmailRoundedIcon, color: '#34d399' },
                { label: 'Trigger automation events', icon: BoltRoundedIcon, color: '#fbbf24' },
              ].map(p => (
                <Box key={p.label} sx={{
                  display: 'flex', alignItems: 'center', gap: 1.25, py: 0.85,
                  borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}`,
                }}>
                  <Box sx={{ width: 28, height: 28, borderRadius: '8px', background: alpha(p.color, isDark ? 0.15 : 0.1), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <p.icon sx={{ fontSize: 14, color: p.color }} />
                  </Box>
                  <Typography sx={{ fontSize: '0.74rem', color: 'text.secondary', flex: 1 }}>{p.label}</Typography>
                  <CheckRoundedIcon sx={{ fontSize: 13, color: '#34d399' }} />
                </Box>
              ))}
              <Box sx={{ mt: 1.5, display: 'flex', alignItems: 'center', gap: 0.75, px: 1, py: 0.75, borderRadius: '9px', background: isDark ? alpha('#34d399', 0.07) : alpha('#34d399', 0.05), border: `1px solid ${alpha('#34d399', 0.15)}` }}>
                <LockRoundedIcon sx={{ fontSize: 13, color: '#34d399' }} />
                <Typography sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>Secure OAuth 2.0 · No passwords stored · Revoke anytime</Typography>
              </Box>
            </Box>
          )}
          {step === 2 && (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 1.5 }}>
              <Box sx={{
                width: 64, height: 64, borderRadius: '18px', mb: 2,
                background: `linear-gradient(135deg, ${alpha(integration.color, 0.2)} 0%, ${alpha(integration.color, 0.08)} 100%)`,
                border: `1.5px solid ${alpha(integration.color, 0.3)}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: `0 8px 24px ${alpha(integration.color, 0.25)}`,
              }}>
                <IntegrationLogo integration={integration} size={40} />
              </Box>
              <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary', mb: 0.5 }}>
                Authorize {integration.name}
              </Typography>
              <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled', textAlign: 'center', mb: 2, lineHeight: 1.6 }}>
                You&apos;ll be redirected to {integration.name} to authorize access. This uses secure OAuth 2.0.
              </Typography>
              <Btn label={`Continue with ${integration.name}`} color={integration.color} icon={OpenInNewRoundedIcon} isDark={isDark} theme={theme} size="md" fullWidth />
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 1.5 }}>
                <VerifiedRoundedIcon sx={{ fontSize: 12, color: '#34d399' }} />
                <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>Verified integration · SOC 2 compliant</Typography>
              </Box>
            </Box>
          )}
          {step === 3 && (
            <Box>
              <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary', mb: 1.5 }}>
                Configure sync preferences
              </Typography>
              {[
                { label: 'Auto-sync new leads', hint: 'Automatically import new leads' },
                { label: 'Trigger automations', hint: 'Fire automation rules on new data' },
                { label: 'Bidirectional sync', hint: 'Push updates back to source' },
              ].map((opt, i) => (
                <Box key={opt.label} sx={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  py: 0.9, borderBottom: i < 2 ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}` : 'none',
                }}>
                  <Box>
                    <Typography sx={{ fontSize: '0.75rem', fontWeight: 500, color: 'text.primary' }}>{opt.label}</Typography>
                    <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>{opt.hint}</Typography>
                  </Box>
                  <Switch defaultChecked size="small" />
                </Box>
              ))}
            </Box>
          )}
        </Box>

        {/* Footer */}
        <Box sx={{
          px: 2.5, pb: 2.5, pt: 1,
          borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <Box component="button" onClick={() => step > 0 && setStep(s => s - 1)} sx={{
            border: 'none', background: 'none', cursor: step > 0 ? 'pointer' : 'default',
            fontSize: '0.72rem', color: step > 0 ? 'text.secondary' : 'text.disabled',
            fontWeight: 500, p: 0,
          }}>
            ← Back
          </Box>
          <Btn
            label={isLast ? '✓ Finish setup' : 'Continue →'}
            color={isLast ? '#34d399' : integration.color}
            onClick={() => isLast ? handleClose() : setStep(s => s + 1)}
            isDark={isDark} theme={theme} size="md"
          />
        </Box>
      </Box>
    </Modal>
  );
}

// ── Email Connect Modal — same flow as Email Accounts page ────────────────────
function EmailConnectModal({ open, onClose, isDark, theme }: {
  open: boolean; onClose: () => void; isDark: boolean; theme: Theme;
}) {
  const [tab, setTab] = useState<'oauth' | 'smtp'>('oauth');
  const [showPass, setShowPass] = useState(false);
  const [smtp, setSmtp] = useState({ name: '', email: '', host: '', port: '587', user: '', pass: '', encryption: 'TLS' });

  const inputSx = {
    px: 1.25,
    py: 0.85,
    borderRadius: '9px',
    fontSize: '0.8rem',
    color: 'text.primary',
    flex: 1,
    background: isDark ? 'rgba(255,255,255,0.04)' : alpha(theme.palette.text.primary, 0.03),
    border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
    '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 },
    '&:focus-within': { borderColor: isDark ? 'rgba(129,140,248,0.5)' : alpha(theme.palette.primary.main, 0.5) },
    transition: 'border-color 0.15s ease',
  };

  const oauthProviders = [
    { id: 'google',    name: 'Google Gmail',      desc: 'Connect via secure OAuth 2.0', color: '#EA4335' },
    { id: 'microsoft', name: 'Microsoft Outlook', desc: 'Connect via Microsoft OAuth',  color: '#0078D4' },
  ];

  return (
    <Modal open={open} onClose={onClose} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
      <Box sx={{
        width: '100%', maxWidth: 440, borderRadius: '18px',
        background: isDark ? '#0f172a' : '#fff',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
        boxShadow: isDark ? '0 32px 80px rgba(0,0,0,0.6)' : '0 32px 80px rgba(15,23,42,0.15)',
        overflow: 'hidden',
        animation: 'modalIn 0.22s ease-out',
        '@keyframes modalIn': { from: { opacity: 0, transform: 'scale(0.96) translateY(8px)' }, to: { opacity: 1, transform: 'scale(1) translateY(0)' } },
      }}>
        <Box sx={{ px: 2.5, pt: 2.5, pb: 2, borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <Box>
            <Typography sx={{ fontSize: '1rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em' }}>Connect Email Account</Typography>
            <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', mt: 0.3 }}>Choose your email provider to get started</Typography>
          </Box>
          <IconButton size="small" onClick={onClose} sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary' }}>
            <CloseRoundedIcon sx={{ fontSize: 15 }} />
          </IconButton>
        </Box>
        <Box sx={{ display: 'flex', gap: 0.5, px: 2, pt: 1.75, pb: 0.25 }}>
          {([{ id: 'oauth', label: 'OAuth Providers' }, { id: 'smtp', label: 'Custom SMTP' }] as const).map(t => (
            <Box key={t.id} component="button" onClick={() => setTab(t.id)} sx={{
              px: 1.25, py: 0.55, borderRadius: '8px', border: 'none', cursor: 'pointer',
              fontSize: '0.72rem', fontWeight: tab === t.id ? 700 : 500,
              background: tab === t.id ? (isDark ? 'rgba(129,140,248,0.18)' : alpha(theme.palette.primary.main, 0.1)) : 'transparent',
              color: tab === t.id ? (isDark ? '#818cf8' : theme.palette.primary.main) : theme.palette.text.secondary,
              transition: 'all 0.15s ease', display: 'flex', alignItems: 'center', gap: 0.5,
            }}>
              {t.id === 'smtp' && <DnsRoundedIcon sx={{ fontSize: 13 }} />}
              {t.label}
            </Box>
          ))}
        </Box>
        {tab === 'oauth' && (
          <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
            {oauthProviders.map(p => (
              <Box key={p.id} component="button" sx={{
                display: 'flex', alignItems: 'center', gap: 1.5, p: 1.5, borderRadius: '12px',
                border: `1.5px solid ${alpha(p.color, isDark ? 0.25 : 0.2)}`,
                background: alpha(p.color, isDark ? 0.1 : 0.06),
                cursor: 'pointer', textAlign: 'left', width: '100%',
                transition: 'all 0.18s ease',
                '&:hover': { transform: 'translateY(-1px)', borderColor: p.color },
              }}>
                <Box sx={{ width: 44, height: 44, borderRadius: '11px', flexShrink: 0, background: isDark ? 'rgba(255,255,255,0.07)' : '#fff', border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(15,23,42,0.08)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Typography sx={{ fontSize: '1rem', fontWeight: 900, color: p.color }}>{p.name[0]}</Typography>
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography sx={{ fontSize: '0.88rem', fontWeight: 700, color: 'text.primary' }}>{p.name}</Typography>
                  <Typography sx={{ fontSize: '0.67rem', color: 'text.secondary', mt: 0.15 }}>{p.desc}</Typography>
                </Box>
                <Box sx={{ px: 1.25, py: 0.5, borderRadius: '8px', flexShrink: 0, background: p.color, color: '#fff', fontSize: '0.68rem', fontWeight: 700 }}>Connect</Box>
              </Box>
            ))}
          </Box>
        )}
        {tab === 'smtp' && (
          <Box sx={{ px: 2, pt: 1.5, pb: 2, display: 'flex', flexDirection: 'column', gap: 1.1 }}>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Account Name</Typography>
                <InputBase value={smtp.name} onChange={e => setSmtp(s => ({ ...s, name: e.target.value }))} placeholder="e.g. Work Email" sx={inputSx} fullWidth />
              </Box>
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>From Email</Typography>
                <InputBase value={smtp.email} onChange={e => setSmtp(s => ({ ...s, email: e.target.value }))} placeholder="you@domain.com" sx={inputSx} fullWidth />
              </Box>
            </Box>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 80px', gap: 1 }}>
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>SMTP Host</Typography>
                <InputBase value={smtp.host} onChange={e => setSmtp(s => ({ ...s, host: e.target.value }))} placeholder="smtp.domain.com" sx={inputSx} fullWidth />
              </Box>
              <Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Port</Typography>
                <InputBase value={smtp.port} onChange={e => setSmtp(s => ({ ...s, port: e.target.value }))} placeholder="587" sx={inputSx} fullWidth />
              </Box>
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Username</Typography>
              <InputBase value={smtp.user} onChange={e => setSmtp(s => ({ ...s, user: e.target.value }))} placeholder="SMTP username" sx={inputSx} fullWidth />
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Password / App Password</Typography>
              <Box sx={{ ...inputSx, display: 'flex', alignItems: 'center', gap: 0.5, px: 1.25, py: 0.85 }}>
                <InputBase type={showPass ? 'text' : 'password'} value={smtp.pass} onChange={e => setSmtp(s => ({ ...s, pass: e.target.value }))} placeholder="••••••••••••"
                  sx={{ flex: 1, fontSize: '0.8rem', color: 'text.primary', '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 } }} />
                <IconButton size="small" onClick={() => setShowPass(v => !v)} sx={{ p: 0.25, color: 'text.disabled' }}>
                  {showPass ? <VisibilityOffRoundedIcon sx={{ fontSize: 15 }} /> : <VisibilityRoundedIcon sx={{ fontSize: 15 }} />}
                </IconButton>
              </Box>
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Encryption</Typography>
              <Box sx={{ display: 'flex', gap: 0.75 }}>
                {['TLS', 'SSL', 'None'].map(enc => (
                  <Box key={enc} component="button" onClick={() => setSmtp(s => ({ ...s, encryption: enc }))} sx={{
                    px: 1.25, py: 0.5, borderRadius: '7px', cursor: 'pointer', fontSize: '0.7rem', fontWeight: 600,
                    background: smtp.encryption === enc ? (isDark ? 'rgba(129,140,248,0.2)' : alpha(theme.palette.primary.main, 0.1)) : (isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04)),
                    color: smtp.encryption === enc ? (isDark ? '#818cf8' : theme.palette.primary.main) : theme.palette.text.secondary,
                    border: `1px solid ${smtp.encryption === enc ? (isDark ? 'rgba(129,140,248,0.3)' : alpha(theme.palette.primary.main, 0.25)) : (isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider)}`,
                    transition: 'all 0.15s ease',
                  }}>{enc}</Box>
                ))}
              </Box>
            </Box>
            <Box component="button" sx={{
              mt: 0.5, width: '100%', border: 'none', cursor: 'pointer', py: 0.9, borderRadius: '10px',
              background: isDark ? 'linear-gradient(135deg, #4f46e5, #818cf8)' : 'linear-gradient(135deg, #4338ca, #6366f1)',
              color: '#fff', fontSize: '0.78rem', fontWeight: 700,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.75,
              transition: 'opacity 0.15s ease, transform 0.15s ease',
              '&:hover': { opacity: 0.88, transform: 'translateY(-1px)' },
            }}>
              <DnsRoundedIcon sx={{ fontSize: 15 }} />
              Connect via SMTP
            </Box>
          </Box>
        )}
        <Box sx={{ mx: 2, mb: 2, px: 1.5, py: 1.1, borderRadius: '10px', background: isDark ? 'rgba(52,211,153,0.07)' : 'rgba(52,211,153,0.05)', border: `1px solid ${isDark ? 'rgba(52,211,153,0.18)' : 'rgba(52,211,153,0.15)'}`, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          {[
            { Icon: LockRoundedIcon,   text: 'Credentials are encrypted and stored securely' },
            { Icon: ShieldRoundedIcon, text: 'Read/send permissions only — no data misuse' },
          ].map(({ Icon, text }) => (
            <Box key={text} sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Icon sx={{ fontSize: 12, color: '#34d399', flexShrink: 0 }} />
              <Typography sx={{ fontSize: '0.65rem', color: isDark ? alpha('#34d399', 0.85) : '#059669', fontWeight: 500 }}>{text}</Typography>
            </Box>
          ))}
        </Box>
      </Box>
    </Modal>
  );
}

// ── Manage panel (slide-in) ───────────────────────────────────────────────────
function ManagePanel({
  integration, open, onClose, isDark, theme,
}: {
  integration: Integration | null; open: boolean; onClose: () => void;
  isDark: boolean; theme: Theme;
}) {
  if (!integration) return null;
  return (
    <Box sx={{
      position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 1300,
      width: { xs: '100vw', sm: 380 },
      background: isDark ? 'linear-gradient(180deg, #1e293b 0%, #0f172a 100%)' : 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
      borderLeft: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'}`,
      boxShadow: `-24px 0 64px ${alpha('#000', isDark ? 0.5 : 0.12)}`,
      transform: open ? 'translateX(0)' : 'translateX(100%)',
      transition: 'transform 0.3s cubic-bezier(0.4,0,0.2,1)',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Header */}
      <Box sx={{ px: 2.5, pt: 2.5, pb: 2, borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)'}`, display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <IntegrationLogo integration={integration} size={40} />
        <Box sx={{ flex: 1 }}>
          <Typography sx={{ fontSize: '0.9rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em' }}>{integration.name}</Typography>
          <StatusDot status={integration.status} isDark={isDark} />
        </Box>
        <IconButton size="small" onClick={onClose} sx={{ color: 'text.disabled', p: 0.5 }}>
          <CloseRoundedIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </Box>

      <Box sx={{ flex: 1, overflowY: 'auto', px: 2.5, py: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {/* Stats */}
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1 }}>
          {[
            { label: 'Leads in', value: integration.leadsImported ?? 0, color: '#34d399' },
            { label: 'Automations', value: integration.automationsTriggered ?? 0, color: '#818cf8' },
            { label: 'Data flow', value: null, text: integration.dataFlow ?? '—', color: '#22d3ee' },
          ].map(s => (
            <Box key={s.label} sx={{ px: 1, py: 0.9, borderRadius: '11px', textAlign: 'center', background: isDark ? alpha(s.color, 0.08) : alpha(s.color, 0.05), border: `1px solid ${alpha(s.color, isDark ? 0.18 : 0.12)}` }}>
              <Typography sx={{ fontSize: s.value !== null ? '1.1rem' : '0.72rem', fontWeight: 800, color: s.color, lineHeight: 1, letterSpacing: '-0.03em' }}>
                {s.value !== null ? <CountUp target={s.value} /> : s.text}
              </Typography>
              <Typography sx={{ fontSize: '0.58rem', color: 'text.disabled', mt: 0.2 }}>{s.label}</Typography>
            </Box>
          ))}
        </Box>

        {/* Sync status */}
        <Box>
          <Typography sx={{ fontSize: '0.6rem', fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'text.disabled', mb: 0.75 }}>Sync Status</Typography>
          <Box sx={{ borderRadius: '12px', border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'}`, overflow: 'hidden', background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.01)' }}>
            {[
              { label: 'Last sync', value: integration.lastSync ?? 'Never' },
              { label: 'Sync frequency', value: 'Every 5 minutes' },
              { label: 'Status', value: integration.status === 'connected' ? 'Healthy' : 'Inactive' },
            ].map((row, i) => (
              <Box key={row.label} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 1.5, py: 0.9, borderBottom: i < 2 ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}` : 'none' }}>
                <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{row.label}</Typography>
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: 'text.primary' }}>{row.value}</Typography>
              </Box>
            ))}
          </Box>
        </Box>

        {/* Data flow controls */}
        <Box>
          <Typography sx={{ fontSize: '0.6rem', fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'text.disabled', mb: 0.75 }}>Data Controls</Typography>
          <Box sx={{ borderRadius: '12px', border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'}`, overflow: 'hidden', background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.01)' }}>
            {[
              { label: 'Auto-sync leads', hint: 'Import new leads automatically' },
              { label: 'Trigger automations', hint: 'Fire rules on new data' },
              { label: 'Bidirectional sync', hint: 'Push updates back to source' },
            ].map((opt, i) => (
              <Box key={opt.label} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 1.5, py: 0.9, borderBottom: i < 2 ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}` : 'none' }}>
                <Box>
                  <Typography sx={{ fontSize: '0.74rem', fontWeight: 500, color: 'text.primary' }}>{opt.label}</Typography>
                  <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>{opt.hint}</Typography>
                </Box>
                <Switch defaultChecked size="small" />
              </Box>
            ))}
          </Box>
        </Box>

        {/* Smart links */}
        <Box>
          <Typography sx={{ fontSize: '0.6rem', fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'text.disabled', mb: 0.75 }}>Use in System</Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
            {[
              { label: 'Use in campaigns', icon: CampaignRoundedIcon, color: '#818cf8' },
              { label: 'Trigger automation', icon: BoltRoundedIcon, color: '#fbbf24' },
              { label: 'View imported leads', icon: PeopleRoundedIcon, color: '#34d399' },
            ].map(link => (
              <Box key={link.label} sx={{
                display: 'flex', alignItems: 'center', gap: 1, px: 1.25, py: 0.85, borderRadius: '10px',
                border: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}`,
                cursor: 'pointer', transition: 'all 0.15s',
                '&:hover': { background: isDark ? alpha(link.color, 0.08) : alpha(link.color, 0.05), borderColor: alpha(link.color, 0.25), transform: 'translateX(2px)' },
              }}>
                <Box sx={{ width: 26, height: 26, borderRadius: '7px', background: alpha(link.color, isDark ? 0.15 : 0.1), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <link.icon sx={{ fontSize: 13, color: link.color }} />
                </Box>
                <Typography sx={{ fontSize: '0.74rem', fontWeight: 500, color: 'text.secondary', flex: 1 }}>{link.label}</Typography>
                <ChevronRightRoundedIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
              </Box>
            ))}
          </Box>
        </Box>
      </Box>

      {/* Footer */}
      <Box sx={{ px: 2.5, pb: 2.5, pt: 1.5, borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}`, display: 'flex', gap: 1 }}>
        <Btn label="Force sync" color="#818cf8" icon={SyncRoundedIcon} isDark={isDark} theme={theme} fullWidth />
        <Btn label="Disconnect" danger icon={LinkOffRoundedIcon} isDark={isDark} theme={theme} fullWidth />
      </Box>
    </Box>
  );
}

// ── Integration row (non-card, horizontal list item) ─────────────────────────
function IntegrationRow({
  integration, isDark, theme, onConnect, onManage, onImportCSV,
}: {
  integration: Integration; isDark: boolean; theme: Theme;
  onConnect: (i: Integration) => void; onManage: (i: Integration) => void;
  onImportCSV: () => void;
}) {
  const isConnected = integration.status === 'connected';
  const isCSV = integration.id === 'csv';
  return (
    <Box sx={{
      display: 'flex', alignItems: 'center', gap: { xs: 1, sm: 1.5 },
      px: { xs: 1.25, sm: 1.5 }, py: 1,
      borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'}`,
      transition: 'background 0.15s ease',
      '&:last-child': { borderBottom: 'none' },
      '&:hover': { background: isDark ? 'rgba(255,255,255,0.025)' : 'rgba(0,0,0,0.018)' },
    }}>
      <IntegrationLogo integration={integration} size={36} />

      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6, flexWrap: 'nowrap', overflow: 'hidden' }}>
          <Typography sx={{ fontSize: '0.8rem', fontWeight: 700, color: 'text.primary', lineHeight: 1.2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {integration.name}
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.4, flexShrink: 0 }}>
            {integration.popular && <GlowChip label="Popular" color="#fbbf24" isDark={isDark} />}
            {integration.new && <GlowChip label="New" color="#34d399" isDark={isDark} />}
            {isCSV && <GlowChip label={`${(integration.leadsImported ?? 0).toLocaleString()} imported`} color="#34d399" isDark={isDark} />}
          </Box>
        </Box>
        <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mt: 0.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {integration.description}
        </Typography>
      </Box>

      {/* Connected meta — desktop only */}
      {isConnected && integration.lastSync && (
        <Box sx={{ display: { xs: 'none', lg: 'flex' }, alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
          <SyncRoundedIcon sx={{ fontSize: 11, color: 'text.disabled' }} />
          <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>{integration.lastSync}</Typography>
        </Box>
      )}

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0 }}>
        {/* CSV: no status dot, just an import button — always available */}
        {isCSV ? (
          <Btn label="Import CSV" color={integration.color} icon={UploadFileRoundedIcon} onClick={onImportCSV} isDark={isDark} theme={theme} size="xs" />
        ) : (
          <>
            <StatusDot status={integration.status} isDark={isDark} />
            {isConnected
              ? <Btn label="Manage" color={integration.color} icon={TuneRoundedIcon} onClick={() => onManage(integration)} isDark={isDark} theme={theme} size="xs" />
              : <Btn label="Connect" color={integration.color} icon={AddRoundedIcon} onClick={() => onConnect(integration)} isDark={isDark} theme={theme} size="xs" />
            }
          </>
        )}
      </Box>
    </Box>
  );
}

// ── Category section ──────────────────────────────────────────────────────────
function CategorySection({
  categoryId, integrations, isDark, theme, onConnect, onManage, onImportCSV,
}: {
  categoryId: CategoryId; integrations: Integration[];
  isDark: boolean; theme: Theme;
  onConnect: (i: Integration) => void; onManage: (i: Integration) => void;
  onImportCSV: () => void;
}) {
  const cat = CATEGORIES.find(c => c.id === categoryId)!;
  const connected = integrations.filter(i => i.status === 'connected').length;

  return (
    <Box sx={{ mb: 2 }}>
      {/* Category header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 0.75, px: 0.25 }}>
        {/* Left: dot + label + description */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0, flex: 1 }}>
          <Box sx={{
            width: 6, height: 6, borderRadius: '50%', background: cat.color,
            boxShadow: `0 0 6px ${alpha(cat.color, 0.6)}`, flexShrink: 0,
          }} />
          <Typography sx={{ fontSize: '0.62rem', fontWeight: 800, letterSpacing: '0.09em', textTransform: 'uppercase', color: cat.color, flexShrink: 0 }}>
            {cat.label}
          </Typography>
          <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled', display: { xs: 'none', sm: 'block' }, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            · {cat.description}
          </Typography>
        </Box>
        {/* Right: connected badge */}
        {connected > 0 && (
          <Box sx={{ px: 0.65, py: 0.15, borderRadius: '5px', flexShrink: 0, background: alpha('#34d399', isDark ? 0.15 : 0.1), border: `1px solid ${alpha('#34d399', 0.25)}` }}>
            <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: '#34d399', whiteSpace: 'nowrap' }}>{connected} connected</Typography>
          </Box>
        )}
      </Box>

      {/* Integration rows container */}
      <Box sx={{
        borderRadius: '14px', overflow: 'hidden',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'}`,
        background: isDark
          ? 'linear-gradient(145deg, rgba(30,41,59,0.6) 0%, rgba(15,23,42,0.4) 100%)'
          : 'linear-gradient(145deg, rgba(255,255,255,0.85) 0%, rgba(248,250,252,0.65) 100%)',
        backdropFilter: 'blur(12px)',
      }}>
        {integrations.map(integration => (
          <IntegrationRow
            key={integration.id}
            integration={integration}
            isDark={isDark}
            theme={theme}
            onConnect={onConnect}
            onManage={onManage}
            onImportCSV={onImportCSV}
          />
        ))}
      </Box>
    </Box>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ══════════════════════════════════════════════════════════════════════════════
export default function IntegrationsPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<CategoryId | 'all'>('all');
  const [connectTarget, setConnectTarget] = useState<Integration | null>(null);
  const [manageTarget, setManageTarget] = useState<Integration | null>(null);
  const [connectOpen, setConnectOpen] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [emailConnectOpen, setEmailConnectOpen] = useState(false);
  const [csvImportOpen, setCsvImportOpen] = useState(false);

  const handleConnect = (i: Integration) => { setConnectTarget(i); setConnectOpen(true); };
  const handleManage  = (i: Integration) => { setManageTarget(i); setManageOpen(true); };

  // Filter integrations
  const filtered = useMemo(() => {
    return INTEGRATIONS.filter(i => {
      const matchCat = activeCategory === 'all' || i.category === activeCategory;
      const matchSearch = !search || i.name.toLowerCase().includes(search.toLowerCase()) || i.description.toLowerCase().includes(search.toLowerCase());
      return matchCat && matchSearch;
    });
  }, [search, activeCategory]);

  // Group by category
  const grouped = useMemo(() => {
    const map = new Map<CategoryId, Integration[]>();
    filtered.forEach(i => {
      if (!map.has(i.category)) map.set(i.category, []);
      map.get(i.category)!.push(i);
    });
    return map;
  }, [filtered]);

  // Global stats
  const totalConnected = INTEGRATIONS.filter(i => i.status === 'connected').length;
  const totalLeads = INTEGRATIONS.reduce((s, i) => s + (i.leadsImported ?? 0), 0);
  const totalAutomations = INTEGRATIONS.reduce((s, i) => s + (i.automationsTriggered ?? 0), 0);

  return (
    <Box sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', minHeight: 0, width: '100%',
      '&::-webkit-scrollbar': { width: 4 },
      '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.18), borderRadius: 2 },
    }}>
      <Box sx={{ width: '100%', boxSizing: 'border-box', px: { xs: 1.5, sm: 2.5, md: 3 }, pt: 2.5, pb: 4 }}>

        {/* ── Page header ── */}
        <Box sx={{
          mb: 2.5,
          animation: 'fadeDown 0.3s ease-out',
          '@keyframes fadeDown': { from: { opacity: 0, transform: 'translateY(-8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        }}>
          {/* Title row */}
          <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 2, mb: 2 }}>
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.9, mb: 0.3 }}>
                <Typography sx={{ fontSize: { xs: '1.15rem', sm: '1.35rem' }, fontWeight: 900, letterSpacing: '-0.03em', color: 'text.primary', lineHeight: 1 }}>
                  Integrations
                </Typography>
                <Box sx={{
                  px: 0.75, py: 0.2, borderRadius: '7px',
                  background: isDark ? alpha('#818cf8', 0.15) : alpha('#818cf8', 0.09),
                  border: `1px solid ${alpha('#818cf8', 0.25)}`,
                  display: 'flex', alignItems: 'center', gap: 0.4,
                }}>
                  <ExtensionRoundedIcon sx={{ fontSize: 10, color: '#818cf8' }} />
                  <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: '#818cf8' }}>{INTEGRATIONS.length} available</Typography>
                </Box>
              </Box>
              <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>
                Connect your tools and automate workflows
              </Typography>
            </Box>
          </Box>

          {/* Stats strip */}
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: { xs: 0.75, sm: 1 }, mb: 2 }}>
            {[
              { label: 'Connected',        value: totalConnected,   color: '#34d399', icon: CheckRoundedIcon },
              { label: 'Leads imported',   value: totalLeads,       color: '#818cf8', icon: PeopleRoundedIcon },
              { label: 'Automations fired',value: totalAutomations, color: '#fbbf24', icon: BoltRoundedIcon },
            ].map(s => (
              <Box key={s.label} sx={{
                px: { xs: 0.75, sm: 1.75 }, py: { xs: 0.85, sm: 1 }, borderRadius: '13px',
                background: isDark ? alpha(s.color, 0.08) : alpha(s.color, 0.05),
                border: `1px solid ${alpha(s.color, isDark ? 0.2 : 0.12)}`,
                display: 'flex', flexDirection: { xs: 'column', sm: 'row' },
                alignItems: { xs: 'flex-start', sm: 'center' }, gap: { xs: 0.4, sm: 1 },
                minWidth: 0, overflow: 'hidden',
              }}>
                <Box sx={{ width: { xs: 22, sm: 30 }, height: { xs: 22, sm: 30 }, borderRadius: '8px', background: alpha(s.color, isDark ? 0.18 : 0.12), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <s.icon sx={{ fontSize: { xs: 11, sm: 14 }, color: s.color }} />
                </Box>
                <Box sx={{ minWidth: 0 }}>
                  <Typography sx={{ fontSize: { xs: '0.88rem', sm: '1.1rem' }, fontWeight: 900, color: s.color, lineHeight: 1, letterSpacing: '-0.04em' }}>
                    <CountUp target={s.value} />
                  </Typography>
                  <Typography sx={{ fontSize: { xs: '0.55rem', sm: '0.58rem' }, color: 'text.disabled', lineHeight: 1.3, mt: 0.15 }}>{s.label}</Typography>
                </Box>
              </Box>
            ))}
          </Box>

          {/* Search + category filter row */}
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
            {/* Search */}
            <Box sx={{
              display: 'flex', alignItems: 'center', gap: 0.75,
              px: 1.25, py: 0.65, borderRadius: '11px', flex: { xs: '1 1 100%', sm: '1 1 220px' },
              background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
              border: `1px solid ${isDark ? 'rgba(255,255,255,0.09)' : 'rgba(0,0,0,0.09)'}`,
              transition: 'border-color 0.15s',
              '&:focus-within': { borderColor: alpha('#818cf8', 0.45) },
            }}>
              <SearchRoundedIcon sx={{ fontSize: 14, color: 'text.disabled', flexShrink: 0 }} />
              <InputBase value={search} onChange={e => setSearch(e.target.value)} placeholder="Search integrations…"
                sx={{ fontSize: '0.76rem', color: 'text.primary', flex: 1, '& input::placeholder': { color: theme.palette.text.disabled } }}
              />
              {search && (
                <Box component="button" onClick={() => setSearch('')} sx={{ border: 'none', background: 'none', cursor: 'pointer', display: 'flex', p: 0, color: theme.palette.text.disabled }}>
                  <CloseRoundedIcon sx={{ fontSize: 13 }} />
                </Box>
              )}
            </Box>

            {/* Category pills */}
            <Box sx={{ display: 'flex', gap: 0.4, flexWrap: 'wrap' }}>
              {[{ id: 'all' as const, label: 'All', color: '#818cf8' }, ...CATEGORIES.map(c => ({ id: c.id, label: c.label, color: c.color }))].map(cat => (
                <Box key={cat.id} component="button" onClick={() => setActiveCategory(cat.id)} sx={{
                  px: 1, py: 0.45, borderRadius: '8px', cursor: 'pointer',
                  background: activeCategory === cat.id ? alpha(cat.color, isDark ? 0.2 : 0.12) : isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
                  color: activeCategory === cat.id ? cat.color : theme.palette.text.secondary,
                  fontSize: '0.68rem', fontWeight: activeCategory === cat.id ? 700 : 500,
                  border: `1px solid ${activeCategory === cat.id ? alpha(cat.color, 0.35) : isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'}`,
                  transition: 'all 0.15s ease',
                  boxShadow: activeCategory === cat.id ? `0 0 8px ${alpha(cat.color, 0.2)}` : 'none',
                  '&:hover': { background: alpha(cat.color, isDark ? 0.12 : 0.08) },
                }}>
                  {cat.label}
                </Box>
              ))}
            </Box>
          </Box>
        </Box>

        {/* ── Integration list ── */}
        {grouped.size === 0 ? (
          <Box sx={{ textAlign: 'center', py: 8 }}>
            <Box sx={{ width: 56, height: 56, borderRadius: '16px', background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'center', mx: 'auto', mb: 1.5 }}>
              <ExtensionRoundedIcon sx={{ fontSize: 24, color: 'text.disabled' }} />
            </Box>
            <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, color: 'text.primary', mb: 0.5 }}>No integrations found</Typography>
            <Typography sx={{ fontSize: '0.72rem', color: 'text.disabled' }}>Try a different search or category filter</Typography>
          </Box>
        ) : (
          <Box sx={{ animation: 'fadeUp 0.25s ease-out', '@keyframes fadeUp': { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } } }}>
            {Array.from(grouped.entries()).map(([catId, items]) => (
              <CategorySection
                key={catId}
                categoryId={catId}
                integrations={items}
                isDark={isDark}
                theme={theme}
                onConnect={handleConnect}
                onManage={handleManage}
                onImportCSV={() => setCsvImportOpen(true)}
              />
            ))}
          </Box>
        )}
      </Box>

      {/* ── Modals & panels ── */}
      <CSVImportModal
        open={csvImportOpen}
        onClose={() => setCsvImportOpen(false)}
      />
      <EmailConnectModal
        open={emailConnectOpen}
        onClose={() => setEmailConnectOpen(false)}
        isDark={isDark}
        theme={theme}
      />
      <ConnectModal
        integration={connectTarget}
        open={connectOpen}
        onClose={() => setConnectOpen(false)}
        isDark={isDark}
        theme={theme}
      />

      {/* Backdrop for manage panel */}
      {manageOpen && (
        <Box onClick={() => setManageOpen(false)} sx={{ position: 'fixed', inset: 0, zIndex: 1299, background: alpha('#000', isDark ? 0.5 : 0.2), backdropFilter: 'blur(2px)' }} />
      )}
      <ManagePanel
        integration={manageTarget}
        open={manageOpen}
        onClose={() => setManageOpen(false)}
        isDark={isDark}
        theme={theme}
      />
    </Box>
  );
}
