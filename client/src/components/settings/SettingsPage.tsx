'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Box, Typography, useTheme, alpha, InputBase, Switch, IconButton, Modal, CircularProgress, MenuItem, TextField, Autocomplete, Chip, type Theme } from '@mui/material';
import { useRouter } from 'next/navigation';
import PersonRoundedIcon from '@mui/icons-material/PersonRounded';
import ManageAccountsRoundedIcon from '@mui/icons-material/ManageAccountsRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import NotificationsRoundedIcon from '@mui/icons-material/NotificationsRounded';
import ShieldRoundedIcon from '@mui/icons-material/ShieldRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import StorageRoundedIcon from '@mui/icons-material/StorageRounded';
import InfoRoundedIcon from '@mui/icons-material/InfoRounded';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import EditRoundedIcon from '@mui/icons-material/EditRounded';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import LockRoundedIcon from '@mui/icons-material/LockRounded';
import DevicesRoundedIcon from '@mui/icons-material/DevicesRounded';
import KeyRoundedIcon from '@mui/icons-material/KeyRounded';
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded';
import ChevronRightRoundedIcon from '@mui/icons-material/ChevronRightRounded';
import MenuRoundedIcon from '@mui/icons-material/MenuRounded';
import CameraAltRoundedIcon from '@mui/icons-material/CameraAltRounded';
import VisibilityOffRoundedIcon from '@mui/icons-material/VisibilityOffRounded';
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded';
import FiberManualRecordRoundedIcon from '@mui/icons-material/FiberManualRecordRounded';
import { lightGradients, darkGradients } from '@/theme/palette';
import { useAuth } from '@/contexts/AuthContext';
import { useLogout } from '@/hooks/mutations/useAuthMutations';
import { useUserSettings } from '@/hooks/queries/useSettings';
import { useUpdateSettings } from '@/hooks/mutations/useSettingsMutations';
import {
  NAV_ITEMS, CONNECTED_ACCOUNTS, ACTIVE_SESSIONS, AI_TONES, AUTOMATION_RULES,
  type SettingSection,
} from './settingsData';

// ── Constants from signup ──────────────────────────────────────────────────────
const BUSINESS_TYPES = ['SaaS', 'Agency', 'E-commerce', 'Freelancer', 'Startup', 'Enterprise', 'Consulting', 'Non-profit', 'Other'];

const INDUSTRIES = ['Technology', 'Marketing', 'Sales', 'Finance', 'Healthcare', 'Education', 'Legal', 'Real Estate', 'Retail', 'Media', 'Logistics', 'HR & Recruiting'];

const COUNTRIES = [
  'India', 'United States', 'United Kingdom', 'Canada', 'Australia',
  'Germany', 'France', 'Netherlands', 'Singapore', 'Brazil', 'Mexico',
  'Spain', 'Italy', 'Japan', 'South Korea', 'UAE', 'South Africa',
  'Nigeria', 'Pakistan', 'Bangladesh', 'Other',
];

const TIMEZONES = [
  'India — Kolkata (UTC+5:30)',
  'United States — New York (UTC-5:00)',
  'United States — Chicago (UTC-6:00)',
  'United States — Denver (UTC-7:00)',
  'United States — Los Angeles (UTC-8:00)',
  'United States — Anchorage (UTC-9:00)',
  'United States — Honolulu (UTC-10:00)',
  'United Kingdom — London (UTC+0:00)',
  'Canada — Toronto (UTC-5:00)',
  'Canada — Vancouver (UTC-8:00)',
  'Australia — Sydney (UTC+10:00)',
  'Australia — Melbourne (UTC+10:00)',
  'Australia — Perth (UTC+8:00)',
  'Germany — Berlin (UTC+1:00)',
  'France — Paris (UTC+1:00)',
  'Netherlands — Amsterdam (UTC+1:00)',
  'Spain — Madrid (UTC+1:00)',
  'Italy — Rome (UTC+1:00)',
  'Sweden — Stockholm (UTC+1:00)',
  'Poland — Warsaw (UTC+1:00)',
  'Finland — Helsinki (UTC+2:00)',
  'Greece — Athens (UTC+2:00)',
  'South Africa — Johannesburg (UTC+2:00)',
  'Egypt — Cairo (UTC+2:00)',
  'Russia — Moscow (UTC+3:00)',
  'Saudi Arabia — Riyadh (UTC+3:00)',
  'UAE — Dubai (UTC+4:00)',
  'Pakistan — Karachi (UTC+5:00)',
  'Bangladesh — Dhaka (UTC+6:00)',
  'Thailand — Bangkok (UTC+7:00)',
  'Vietnam — Ho Chi Minh (UTC+7:00)',
  'Indonesia — Jakarta (UTC+7:00)',
  'China — Beijing (UTC+8:00)',
  'Singapore — Singapore (UTC+8:00)',
  'Malaysia — Kuala Lumpur (UTC+8:00)',
  'Philippines — Manila (UTC+8:00)',
  'South Korea — Seoul (UTC+9:00)',
  'Japan — Tokyo (UTC+9:00)',
  'New Zealand — Auckland (UTC+12:00)',
  'Brazil — São Paulo (UTC-3:00)',
  'Argentina — Buenos Aires (UTC-3:00)',
  'Mexico — Mexico City (UTC-6:00)',
  'Nigeria — Lagos (UTC+1:00)',
  'Kenya — Nairobi (UTC+3:00)',
];

const TONES = [
  { key: 'professional', label: 'Professional', desc: 'Formal, clear, business-focused' },
  { key: 'friendly',     label: 'Friendly',     desc: 'Warm, approachable, conversational' },
  { key: 'sales',        label: 'Sales-driven', desc: 'Persuasive, action-oriented' },
  { key: 'custom',       label: 'Custom',        desc: 'AI learns from your writing style' },
];

const USE_CASES = [
  { key: 'sales',     label: 'Sales outreach' },
  { key: 'support',   label: 'Customer support' },
  { key: 'followups', label: 'Follow-ups' },
  { key: 'outreach',  label: 'Cold outreach' },
];

// ── Icon map ──────────────────────────────────────────────────────────────────
const ICON_MAP: Record<string, React.ElementType> = {
  person: PersonRoundedIcon, manage: ManageAccountsRoundedIcon, email: EmailRoundedIcon,
  ai: AutoAwesomeRoundedIcon, bolt: BoltRoundedIcon, bell: NotificationsRoundedIcon,
  shield: ShieldRoundedIcon, group: GroupsRoundedIcon, storage: StorageRoundedIcon, info: InfoRoundedIcon,
};

// ── Animated counter ──────────────────────────────────────────────────────────
function CountUp({ target }: { target: number }) {
  const [val, setVal] = useState(0);
  const frame = useRef<number | null>(null);
  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / 900, 1);
      setVal(Math.round((1 - Math.pow(1 - p, 3)) * target));
      if (p < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => { if (frame.current) cancelAnimationFrame(frame.current); };
  }, [target]);
  return <>{val.toLocaleString()}</>;
}

// ── Glass cluster — groups related fields together ────────────────────────────
function Cluster({
  children, isDark, theme, label, labelColor, action,
}: {
  children: React.ReactNode; isDark: boolean; theme: Theme;
  label?: string; labelColor?: string; action?: React.ReactNode;
}) {
  return (
    <Box sx={{ mb: 2.5 }}>
      {(label || action) && (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.75, px: 0.25 }}>
          {label && (
            <Typography sx={{
              fontSize: '0.6rem', fontWeight: 800, letterSpacing: '0.1em',
              textTransform: 'uppercase', color: labelColor ?? 'text.disabled',
            }}>
              {label}
            </Typography>
          )}
          {action}
        </Box>
      )}
      <Box sx={{
        borderRadius: '14px', overflow: 'hidden',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'}`,
        background: isDark
          ? 'linear-gradient(145deg, rgba(30,41,59,0.7) 0%, rgba(15,23,42,0.5) 100%)'
          : 'linear-gradient(145deg, rgba(255,255,255,0.9) 0%, rgba(248,250,252,0.7) 100%)',
        backdropFilter: 'blur(12px)',
      }}>
        {children}
      </Box>
    </Box>
  );
}

// ── Field row inside a cluster ────────────────────────────────────────────────
function FieldRow({
  label, hint, children, isDark, theme, last = false, danger = false,
}: {
  label: string; hint?: string; children: React.ReactNode;
  isDark: boolean; theme: Theme; last?: boolean; danger?: boolean;
}) {
  return (
    <Box sx={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      gap: 2, px: 1.5, py: 1.1,
      borderBottom: last ? 'none' : `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}`,
      transition: 'background 0.15s',
      '&:hover': { background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)' },
    }}>
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontSize: '0.78rem', fontWeight: 500, color: danger ? '#f87171' : 'text.primary', lineHeight: 1.3 }}>
          {label}
        </Typography>
        {hint && <Typography sx={{ fontSize: '0.63rem', color: 'text.disabled', mt: 0.1, lineHeight: 1.4 }}>{hint}</Typography>}
      </Box>
      <Box sx={{ flexShrink: 0 }}>{children}</Box>
    </Box>
  );
}

// ── Inline editable field ─────────────────────────────────────────────────────
function EditField({
  value, placeholder, isDark, theme, type = 'text', fullWidth = false, onChange,
}: {
  value: string; placeholder?: string; isDark: boolean; theme: Theme;
  type?: string; fullWidth?: boolean; onChange?: (value: string) => void;
}) {
  const [val, setVal] = useState(value);
  const [focused, setFocused] = useState(false);
  const [show, setShow] = useState(false);
  const isPass = type === 'password';

  useEffect(() => {
    setVal(value);
  }, [value]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setVal(newValue);
    onChange?.(newValue);
  };

  return (
    <Box sx={{
      display: 'flex', alignItems: 'center', gap: 0.5,
      px: 1.1, py: 0.55, borderRadius: '9px',
      width: fullWidth ? '100%' : 190,
      background: focused
        ? isDark ? 'rgba(129,140,248,0.1)' : alpha('#818cf8', 0.06)
        : isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
      border: `1px solid ${focused ? alpha('#818cf8', 0.45) : isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`,
      transition: 'all 0.15s ease',
    }}>
      <InputBase
        value={val}
        onChange={handleChange}
        placeholder={placeholder}
        type={isPass && !show ? 'password' : 'text'}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        sx={{ fontSize: '0.78rem', color: 'text.primary', flex: 1, '& input': { p: 0 } }}
      />
      {isPass && (
        <Box component="button" onClick={() => setShow(v => !v)} sx={{ border: 'none', background: 'none', cursor: 'pointer', display: 'flex', p: 0, color: theme.palette.text.disabled }}>
          {show ? <VisibilityRoundedIcon sx={{ fontSize: 13 }} /> : <VisibilityOffRoundedIcon sx={{ fontSize: 13 }} />}
        </Box>
      )}
    </Box>
  );
}

// ── Pill toggle ───────────────────────────────────────────────────────────────
function PillToggle<T extends string>({
  options, value, onChange, isDark, theme, color = '#818cf8',
}: {
  options: { id: T; label: string }[]; value: T; onChange: (v: T) => void;
  isDark: boolean; theme: Theme; color?: string;
}) {
  return (
    <Box sx={{
      display: 'inline-flex', gap: 0.2, p: 0.25, borderRadius: '9px',
      background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
      border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
    }}>
      {options.map(opt => (
        <Box key={opt.id} component="button" onClick={() => onChange(opt.id)} sx={{
          px: 1, py: 0.4, borderRadius: '7px', border: 'none', cursor: 'pointer',
          background: value === opt.id ? alpha(color, isDark ? 0.22 : 0.14) : 'transparent',
          color: value === opt.id ? color : theme.palette.text.secondary,
          fontSize: '0.68rem', fontWeight: value === opt.id ? 700 : 500,
          transition: 'all 0.15s ease',
          boxShadow: value === opt.id ? `0 0 8px ${alpha(color, 0.25)}` : 'none',
        }}>
          {opt.label}
        </Box>
      ))}
    </Box>
  );
}

// ── Glow chip / badge ─────────────────────────────────────────────────────────
function GlowChip({ label, color, isDark }: { label: string; color: string; isDark: boolean }) {
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.4,
      px: 0.75, py: 0.2, borderRadius: '6px',
      background: alpha(color, isDark ? 0.15 : 0.1),
      border: `1px solid ${alpha(color, isDark ? 0.3 : 0.2)}`,
      boxShadow: `0 0 8px ${alpha(color, 0.2)}`,
    }}>
      <FiberManualRecordRoundedIcon sx={{ fontSize: 6, color }} />
      <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color, lineHeight: 1 }}>{label}</Typography>
    </Box>
  );
}

// ── Compact action button ─────────────────────────────────────────────────────
function Btn({
  label, color = '#818cf8', onClick, icon: Icon, danger = false, isDark, theme, size = 'sm',
}: {
  label: string; color?: string; onClick?: () => void; icon?: React.ElementType;
  danger?: boolean; isDark: boolean; theme: Theme; size?: 'sm' | 'xs';
}) {
  const c = danger ? '#f87171' : color;
  return (
    <Box component="button" onClick={onClick} sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.5,
      px: size === 'xs' ? 0.9 : 1.25, py: size === 'xs' ? 0.35 : 0.55,
      borderRadius: '8px',
      border: `1px solid ${alpha(c, isDark ? 0.3 : 0.22)}`,
      background: alpha(c, isDark ? 0.1 : 0.07),
      color: c, fontSize: size === 'xs' ? '0.65rem' : '0.72rem', fontWeight: 600,
      cursor: 'pointer', transition: 'all 0.15s ease',
      '&:hover': {
        background: alpha(c, isDark ? 0.2 : 0.14),
        borderColor: alpha(c, 0.5),
        boxShadow: `0 0 10px ${alpha(c, 0.2)}`,
        transform: 'translateY(-1px)',
      },
    }}>
      {Icon && <Icon sx={{ fontSize: size === 'xs' ? 11 : 13 }} />}
      {label}
    </Box>
  );
}

// ── Section heading ───────────────────────────────────────────────────────────
function SectionHead({
  title, subtitle, color, icon: Icon, isDark,
}: {
  title: string; subtitle: string; color: string; icon: React.ElementType; isDark: boolean;
}) {
  return (
    <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1.25 }}>
      <Box sx={{
        width: 36, height: 36, borderRadius: '10px', flexShrink: 0,
        background: `linear-gradient(135deg, ${alpha(color, isDark ? 0.25 : 0.15)} 0%, ${alpha(color, isDark ? 0.1 : 0.06)} 100%)`,
        border: `1px solid ${alpha(color, isDark ? 0.3 : 0.2)}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: `0 0 16px ${alpha(color, 0.2)}`,
      }}>
        <Icon sx={{ fontSize: 17, color }} />
      </Box>
      <Box>
        <Typography sx={{ fontSize: '1rem', fontWeight: 800, letterSpacing: '-0.025em', color: 'text.primary', lineHeight: 1.1 }}>
          {title}
        </Typography>
        <Typography sx={{ fontSize: '0.67rem', color: 'text.disabled', mt: 0.15 }}>{subtitle}</Typography>
      </Box>
    </Box>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// PROFILE
// ══════════════════════════════════════════════════════════════════════════════
function ProfileSection({ isDark, theme }: { isDark: boolean; theme: Theme }) {
  const router = useRouter();
  const { user, getAccessToken, getRefreshToken, clearAuth, updateUser } = useAuth();
  const logoutMutation = useLogout();
  const grad = isDark ? darkGradients : lightGradients;
  const color = '#818cf8';

  // Local state for editable fields
  const [editedName, setEditedName] = useState(user?.full_name || '');
  const [editedEmail, setEditedEmail] = useState(user?.email || '');
  const [editedCompany, setEditedCompany] = useState(user?.business_name || '');
  const [editedIndustry, setEditedIndustry] = useState(user?.business_type || '');
  const [editedCountry, setEditedCountry] = useState(user?.country || '');
  const [editedTimezone, setEditedTimezone] = useState(user?.timezone || '');
  const [editedIndustries, setEditedIndustries] = useState<string[]>(user?.industries || []);

  // Sync local state when user data changes
  useEffect(() => {
    if (user) {
      setEditedName(user.full_name || '');
      setEditedEmail(user.email || '');
      setEditedCompany(user.business_name || '');
      setEditedIndustry(user.business_type || '');
      setEditedCountry(user.country || '');
      setEditedTimezone(user.timezone || '');
      setEditedIndustries(user.industries || []);
    }
  }, [user]);

  const handleLogout = async () => {
    try {
      const accessToken = getAccessToken();
      const refreshToken = getRefreshToken();
      
      if (!accessToken || !refreshToken) {
        clearAuth();
        router.push('/sign-in');
        return;
      }

      // Call logout API to invalidate tokens on server
      await logoutMutation.mutateAsync({ refresh_token: refreshToken });

      // Clear local auth state
      clearAuth();

      // Redirect to signin
      router.push('/sign-in');
    } catch (error) {
      console.error('[ProfileSection] Logout failed:', error);
      // Even if API call fails, clear local state and redirect
      clearAuth();
      router.push('/sign-in');
    }
  };

  const handleSaveChanges = () => {
    // Update AuthContext with new values
    updateUser({
      full_name: editedName,
      email: editedEmail,
      business_name: editedCompany,
      business_type: editedIndustry,
      country: editedCountry,
      timezone: editedTimezone,
      industries: editedIndustries,
    });
    // TODO: Call API to persist changes to backend
  };

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      fontSize: '0.78rem',
      borderRadius: '9px',
      '&.Mui-focused': {
        boxShadow: `0 0 0 3px ${alpha(theme.palette.primary.main, isDark ? 0.16 : 0.10)}`,
      },
    },
    '& .MuiInputLabel-root': { fontSize: '0.78rem' },
    '& .MuiSelect-select': { fontSize: '0.78rem' },
  };
  return (
    <Box>
      <SectionHead title="Profile" subtitle="Your identity and business details" color={color} icon={PersonRoundedIcon} isDark={isDark} />

      {/* Avatar hero */}
      <Box sx={{
        mb: 2.5, px: 2, py: 2, borderRadius: '14px',
        background: isDark
          ? `linear-gradient(135deg, ${alpha(color, 0.12)} 0%, rgba(15,23,42,0.4) 100%)`
          : `linear-gradient(135deg, ${alpha(color, 0.07)} 0%, rgba(248,250,252,0.6) 100%)`,
        border: `1px solid ${alpha(color, isDark ? 0.2 : 0.12)}`,
        display: 'flex', alignItems: 'center', gap: 2,
      }}>
        <Box sx={{ position: 'relative', flexShrink: 0 }}>
          <Box sx={{
            width: 64, height: 64, borderRadius: '16px',
            background: grad.primary,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: `0 8px 24px ${alpha(color, 0.35)}`,
          }}>
            <Typography sx={{ fontSize: '1.5rem', fontWeight: 900, color: '#fff', letterSpacing: '-0.04em' }}>
              {user?.full_name ? user.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2) : 'JD'}
            </Typography>
          </Box>
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontSize: '0.95rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em' }}>{user?.full_name || 'John Doe'}</Typography>
          <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled' }}>{user?.email || 'john@company.com'}</Typography>
          <Box sx={{ display: 'flex', gap: 0.75, mt: 0.75 }}>
            <GlowChip label="Pro Plan" color={color} isDark={isDark} />
            <GlowChip label="Admin" color="#34d399" isDark={isDark} />
          </Box>
        </Box>
        <Box component="button" onClick={handleLogout} disabled={logoutMutation.isPending} sx={{
          display: 'inline-flex', alignItems: 'center', gap: 0.5,
          px: 1.25, py: 0.55, borderRadius: '8px',
          border: `1px solid ${alpha('#f87171', isDark ? 0.3 : 0.22)}`,
          background: alpha('#f87171', isDark ? 0.1 : 0.07),
          color: '#f87171', fontSize: '0.72rem', fontWeight: 600,
          cursor: 'pointer', transition: 'all 0.15s ease',
          '&:hover': {
            background: alpha('#f87171', isDark ? 0.2 : 0.14),
            borderColor: alpha('#f87171', 0.5),
            boxShadow: `0 0 10px ${alpha('#f87171', 0.2)}`,
            transform: 'translateY(-1px)',
          },
          '&:disabled': { opacity: 0.5, cursor: 'not-allowed' },
        }}>
          {logoutMutation.isPending ? <CircularProgress size={11} sx={{ color: '#f87171' }} /> : null}
          {logoutMutation.isPending ? 'Logging out...' : 'Logout'}
        </Box>
      </Box>

      <Cluster label="Identity" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Full name" isDark={isDark} theme={theme}>
          <EditField value={editedName} onChange={(val) => setEditedName(val)} isDark={isDark} theme={theme} />
        </FieldRow>
        <FieldRow label="Email address" hint="Login & notifications" isDark={isDark} theme={theme}>
          <EditField value={editedEmail} onChange={(val) => setEditedEmail(val)} isDark={isDark} theme={theme} />
        </FieldRow>
        <FieldRow label="Country" isDark={isDark} theme={theme}>
          <Box sx={{ width: 190 }}>
            <TextField
              select
              value={editedCountry}
              onChange={(e) => setEditedCountry(e.target.value)}
              size="small"
              fullWidth
              sx={inputSx}
            >
              {COUNTRIES.map(c => <MenuItem key={c} value={c} sx={{ fontSize: '0.78rem' }}>{c}</MenuItem>)}
            </TextField>
          </Box>
        </FieldRow>
        <FieldRow label="Timezone" isDark={isDark} theme={theme} last>
          <Box sx={{ width: 190 }}>
            <TextField
              select
              value={editedTimezone}
              onChange={(e) => setEditedTimezone(e.target.value)}
              size="small"
              fullWidth
              sx={inputSx}
              SelectProps={{ MenuProps: { PaperProps: { sx: { maxHeight: 280 } } } }}
            >
              {TIMEZONES.map(t => (
                <MenuItem key={t} value={t} sx={{ fontSize: '0.72rem', whiteSpace: 'normal', lineHeight: 1.4, py: 0.75 }}>
                  {t}
                </MenuItem>
              ))}
            </TextField>
          </Box>
        </FieldRow>
      </Cluster>

      <Cluster label="Business" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Company name" isDark={isDark} theme={theme}>
          <EditField value={editedCompany} onChange={(val) => setEditedCompany(val)} isDark={isDark} theme={theme} />
        </FieldRow>
        <FieldRow label="Business type" isDark={isDark} theme={theme}>
          <Box sx={{ width: 190 }}>
            <TextField
              select
              value={editedIndustry}
              onChange={(e) => setEditedIndustry(e.target.value)}
              size="small"
              fullWidth
              sx={inputSx}
            >
              {BUSINESS_TYPES.map(t => <MenuItem key={t} value={t} sx={{ fontSize: '0.78rem' }}>{t}</MenuItem>)}
            </TextField>
          </Box>
        </FieldRow>
        <Box sx={{
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
          gap: 2, px: 1.5, py: 1.1,
          borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}`,
          transition: 'background 0.15s',
          '&:hover': { background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)' },
        }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontSize: '0.78rem', fontWeight: 500, color: 'text.primary', lineHeight: 1.3 }}>
              Industries
            </Typography>
            <Typography sx={{ fontSize: '0.63rem', color: 'text.disabled', mt: 0.1, lineHeight: 1.4 }}>Multiple industries</Typography>
          </Box>
          <Box sx={{ flexShrink: 0, width: 190 }}>
            <Autocomplete
              multiple
              options={INDUSTRIES}
              value={editedIndustries}
              onChange={(_, v) => setEditedIndustries(v)}
              size="small"
              renderTags={(val, getTagProps) =>
                val.map((opt, i) => (
                  <Chip {...getTagProps({ index: i })} key={opt} label={opt} size="small"
                    sx={{ fontSize: '0.65rem', height: 20, '& .MuiChip-deleteIcon': { fontSize: 12 } }} />
                ))
              }
              renderInput={(params) => (
                <TextField {...params} placeholder="Select industries" sx={inputSx} />
              )}
              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '9px', fontSize: '0.78rem' } }}
            />
          </Box>
        </Box>
        <FieldRow label="Website" isDark={isDark} theme={theme} last>
          <EditField value="https://acme.com" isDark={isDark} theme={theme} />
        </FieldRow>
      </Cluster>

      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Btn label="Save changes" color={color} icon={CheckRoundedIcon} onClick={handleSaveChanges} isDark={isDark} theme={theme} />
      </Box>
    </Box>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// ACCOUNT
// ══════════════════════════════════════════════════════════════════════════════
function AccountSection({ isDark, theme, settings, updateSettings }: { isDark: boolean; theme: Theme; settings?: any; updateSettings?: any }) {
  const [twoFA, setTwoFA] = useState(settings?.two_factor_enabled ?? false);
  const [showQR, setShowQR] = useState(false);
  const color = '#22d3ee';
  
  useEffect(() => {
    if (settings?.two_factor_enabled !== undefined) {
      setTwoFA(settings.two_factor_enabled);
    }
  }, [settings]);
  
  const handleToggle2FA = async (enabled: boolean) => {
    setTwoFA(enabled);
    if (updateSettings) {
      await updateSettings.mutateAsync({ two_factor_enabled: enabled });
    }
  };
  
  return (
    <Box>
      <SectionHead title="Account" subtitle="Password, 2FA, and active sessions" color={color} icon={ManageAccountsRoundedIcon} isDark={isDark} />

      <Cluster label="Password" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Current password" isDark={isDark} theme={theme}>
          <EditField value="password123" type="password" isDark={isDark} theme={theme} />
        </FieldRow>
        <FieldRow label="New password" isDark={isDark} theme={theme}>
          <EditField value="" placeholder="New password" type="password" isDark={isDark} theme={theme} />
        </FieldRow>
        <FieldRow label="Confirm password" isDark={isDark} theme={theme} last>
          <EditField value="" placeholder="Confirm password" type="password" isDark={isDark} theme={theme} />
        </FieldRow>
      </Cluster>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2.5 }}>
        <Btn label="Update password" color={color} icon={LockRoundedIcon} isDark={isDark} theme={theme} />
      </Box>

      <Cluster label="Two-Factor Auth" labelColor={color} isDark={isDark} theme={theme}
        action={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            <GlowChip label={twoFA ? 'Enabled' : 'Disabled'} color={twoFA ? '#34d399' : '#f87171'} isDark={isDark} />
            <Switch checked={twoFA} onChange={e => handleToggle2FA(e.target.checked)} size="small" />
          </Box>
        }
      >
        <Box sx={{ px: 1.5, py: 1.25 }}>
          <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', lineHeight: 1.6 }}>
            {twoFA
              ? '✓ Your account is protected with email-based 2FA. A verification code will be sent to your email on each login.'
              : 'Add an extra layer of security by requiring a verification code sent to your email on each login.'}
          </Typography>
          {!twoFA && (
            <Box sx={{ mt: 1 }}>
              <Btn label="Enable 2FA" color={color} icon={KeyRoundedIcon} onClick={() => setShowQR(true)} isDark={isDark} theme={theme} />
            </Box>
          )}
          {twoFA && (
            <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
              <Btn label="Disable 2FA" danger icon={CloseRoundedIcon} onClick={() => setTwoFA(false)} isDark={isDark} theme={theme} size="xs" />
            </Box>
          )}
        </Box>
      </Cluster>

      {/* 2FA Setup Modal */}
      <Modal open={showQR} onClose={() => setShowQR(false)}>
        <Box sx={{
          position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
          width: 400, borderRadius: '18px', p: 3, outline: 'none',
          background: isDark ? '#1e293b' : '#fff',
          border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
          boxShadow: `0 24px 64px ${alpha('#000', 0.4)}`,
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <KeyRoundedIcon sx={{ color, fontSize: 20 }} />
            <Typography sx={{ fontSize: '0.95rem', fontWeight: 800, color: 'text.primary' }}>Enable Two-Factor Authentication</Typography>
          </Box>
          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mb: 2, lineHeight: 1.7 }}>
            When you enable 2FA, you'll receive a verification code via email every time you sign in. This adds an extra layer of security to your account.
          </Typography>
          <Box sx={{
            p: 2, borderRadius: '12px', mb: 2,
            background: isDark ? alpha(color, 0.08) : alpha(color, 0.05),
            border: `1px solid ${alpha(color, isDark ? 0.2 : 0.12)}`,
          }}>
            <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', mb: 1 }}>How it works:</Typography>
            <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', lineHeight: 1.6 }}>
              1. Enter your email and password<br />
              2. Receive a 6-digit code via email<br />
              3. Enter the code to complete login
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
            <Btn label="Cancel" isDark={isDark} theme={theme} onClick={() => setShowQR(false)} />
            <Btn label="Enable 2FA" color={color} icon={CheckRoundedIcon} onClick={() => { setTwoFA(true); setShowQR(false); }} isDark={isDark} theme={theme} />
          </Box>
        </Box>
      </Modal>

      <Cluster label="Active Sessions" labelColor={color} isDark={isDark} theme={theme}
        action={<Btn label="Revoke all" color="#f87171" isDark={isDark} theme={theme} size="xs" />}
      >
        {ACTIVE_SESSIONS.map((s, i) => (
          <FieldRow key={s.id} label={s.device} hint={`${s.location} · ${s.time}`} isDark={isDark} theme={theme} last={i === ACTIVE_SESSIONS.length - 1}>
            {s.current
              ? <GlowChip label="This device" color={color} isDark={isDark} />
              : <Btn label="Revoke" danger isDark={isDark} theme={theme} size="xs" />}
          </FieldRow>
        ))}
      </Cluster>
    </Box>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// EMAIL ACCOUNTS
// ══════════════════════════════════════════════════════════════════════════════
function EmailSection({ isDark, theme, settings, updateSettings }: { isDark: boolean; theme: Theme; settings?: any; updateSettings?: any }) {
  const [defaultAcc, setDefaultAcc] = useState('1');
  const [syncFreq, setSyncFreq] = useState<'5m' | '15m' | '30m'>(settings?.sync_frequency ?? '5m');
  const [autoSync, setAutoSync] = useState(settings?.auto_sync_replies ?? true);
  const [syncSent, setSyncSent] = useState(settings?.sync_sent_folder ?? true);
  const color = '#34d399';
  
  useEffect(() => {
    if (settings) {
      setSyncFreq(settings.sync_frequency ?? '5m');
      setAutoSync(settings.auto_sync_replies ?? true);
      setSyncSent(settings.sync_sent_folder ?? true);
    }
  }, [settings]);
  
  const handleUpdateSetting = async (key: string, value: any) => {
    if (updateSettings) {
      await updateSettings.mutateAsync({ [key]: value });
    }
  };
  return (
    <Box>
      <SectionHead title="Email Accounts" subtitle="Connected accounts and sync settings" color={color} icon={EmailRoundedIcon} isDark={isDark} />

      <Cluster label="Connected Accounts" labelColor={color} isDark={isDark} theme={theme}
        action={<Btn label="Add account" color={color} icon={AddRoundedIcon} isDark={isDark} theme={theme} size="xs" />}
      >
        {CONNECTED_ACCOUNTS.map((acc, i) => (
          <Box key={acc.id} sx={{
            display: 'flex', alignItems: 'center', gap: 1.25, px: 1.5, py: 1.1,
            borderBottom: i < CONNECTED_ACCOUNTS.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}` : 'none',
            transition: 'background 0.15s',
            '&:hover': { background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)' },
          }}>
            <Box sx={{
              width: 34, height: 34, borderRadius: '9px', flexShrink: 0,
              background: alpha(color, isDark ? 0.12 : 0.08),
              border: `1px solid ${alpha(color, isDark ? 0.2 : 0.12)}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <EmailRoundedIcon sx={{ fontSize: 15, color }} />
            </Box>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography sx={{ fontSize: '0.76rem', fontWeight: 600, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {acc.email}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.15 }}>
                <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>{acc.provider}</Typography>
                {/* Health bar */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                  <Box sx={{ width: 36, height: 3, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)', overflow: 'hidden' }}>
                    <Box sx={{ height: '100%', width: `${acc.health}%`, borderRadius: 2, background: acc.health >= 85 ? '#34d399' : '#fbbf24', transition: 'width 0.8s ease' }} />
                  </Box>
                  <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: acc.health >= 85 ? '#34d399' : '#fbbf24' }}>{acc.health}%</Typography>
                </Box>
              </Box>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexShrink: 0 }}>
              {defaultAcc === acc.id
                ? <GlowChip label="Default" color={color} isDark={isDark} />
                : <Btn label="Set default" color={color} onClick={() => setDefaultAcc(acc.id)} isDark={isDark} theme={theme} size="xs" />}
              <IconButton size="small" sx={{ color: 'text.disabled', '&:hover': { color: '#f87171' }, p: 0.4 }}>
                <DeleteOutlineRoundedIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Box>
          </Box>
        ))}
      </Cluster>

      <Cluster label="Sync Preferences" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Auto-sync replies" hint="Pull new replies every 5 minutes" isDark={isDark} theme={theme}>
          <Switch checked={autoSync} onChange={e => { setAutoSync(e.target.checked); handleUpdateSetting('auto_sync_replies', e.target.checked); }} size="small" />
        </FieldRow>
        <FieldRow label="Sync sent folder" hint="Track emails sent outside the platform" isDark={isDark} theme={theme}>
          <Switch checked={syncSent} onChange={e => { setSyncSent(e.target.checked); handleUpdateSetting('sync_sent_folder', e.target.checked); }} size="small" />
        </FieldRow>
        <FieldRow label="Sync frequency" isDark={isDark} theme={theme} last>
          <PillToggle options={[{ id: '5m', label: '5m' }, { id: '15m', label: '15m' }, { id: '30m', label: '30m' }]} value={syncFreq} onChange={(v) => { setSyncFreq(v); handleUpdateSetting('sync_frequency', v); }} color={color} isDark={isDark} theme={theme} />
        </FieldRow>
      </Cluster>
    </Box>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// AI SETTINGS
// ══════════════════════════════════════════════════════════════════════════════
function AISection({ isDark, theme, settings, updateSettings }: { isDark: boolean; theme: Theme; settings?: any; updateSettings?: any }) {
  const { user } = useAuth();
  const [tone, setTone] = useState(user?.communication_tone || 'professional');
  const [autoLevel, setAutoLevel] = useState<'off' | 'assist' | 'auto'>(settings?.automation_level ?? 'assist');
  const [maxReplyLength, setMaxReplyLength] = useState<'short' | 'medium' | 'long'>(settings?.max_reply_length ?? 'medium');
  const [customInstructions, setCustomInstructions] = useState(user?.business_description || '');
  const [targetAudience, setTargetAudience] = useState(user?.target_audience || '');
  const [useCases, setUseCases] = useState<string[]>(user?.use_cases || []);
  const [learnFromEdits, setLearnFromEdits] = useState(settings?.learn_from_edits ?? true);
  const [personalizePerLead, setPersonalizePerLead] = useState(settings?.personalize_per_lead ?? true);
  const [avoidRepetition, setAvoidRepetition] = useState(settings?.avoid_repetition ?? true);
  const color = '#c084fc';

  // Sync with settings data
  useEffect(() => {
    if (settings) {
      setAutoLevel(settings.automation_level ?? 'assist');
      setMaxReplyLength(settings.max_reply_length ?? 'medium');
      setLearnFromEdits(settings.learn_from_edits ?? true);
      setPersonalizePerLead(settings.personalize_per_lead ?? true);
      setAvoidRepetition(settings.avoid_repetition ?? true);
    }
  }, [settings]);
  
  // Sync with user data
  useEffect(() => {
    if (user?.communication_tone) setTone(user.communication_tone);
    if (user?.business_description) setCustomInstructions(user.business_description);
    if (user?.target_audience) setTargetAudience(user.target_audience);
    if (user?.use_cases) setUseCases(user.use_cases);
  }, [user]);
  
  const handleUpdateSetting = async (key: string, value: any) => {
    if (updateSettings) {
      await updateSettings.mutateAsync({ [key]: value });
    }
  };

  return (
    <Box>
      <SectionHead title="AI Settings" subtitle="Tone, behavior, and custom instructions" color={color} icon={AutoAwesomeRoundedIcon} isDark={isDark} />

      {/* AI status strip */}
      <Box sx={{
        mb: 2.5, px: 1.5, py: 1.1, borderRadius: '12px',
        background: isDark ? alpha(color, 0.08) : alpha(color, 0.05),
        border: `1px solid ${alpha(color, isDark ? 0.2 : 0.12)}`,
        display: 'flex', alignItems: 'center', gap: 1.5,
      }}>
        <Box sx={{ width: 8, height: 8, borderRadius: '50%', background: color, boxShadow: `0 0 8px ${alpha(color, 0.7)}`, animation: 'pulse 2s ease-in-out infinite', '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.4 } }, flexShrink: 0 }} />
        <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', flex: 1 }}>
          AI engine is <Box component="span" sx={{ color, fontWeight: 700 }}>active</Box> · GPT-4o · Last used 2 minutes ago
        </Typography>
        <GlowChip label="Online" color={color} isDark={isDark} />
      </Box>

      {/* Tone selector */}
      <Cluster label="Response Tone" labelColor={color} isDark={isDark} theme={theme}>
        {TONES.map((t, i) => (
          <Box key={t.key} component="button" onClick={() => setTone(t.key)} sx={{
            display: 'flex', alignItems: 'center', gap: 1.25, width: '100%',
            px: 1.5, py: 0.95, border: 'none', cursor: 'pointer', textAlign: 'left',
            background: tone === t.key ? alpha(color, isDark ? 0.1 : 0.06) : 'transparent',
            borderBottom: i < TONES.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}` : 'none',
            transition: 'background 0.15s',
            '&:hover': { background: alpha(color, isDark ? 0.07 : 0.04) },
          }}>
            <Box sx={{
              width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
              background: tone === t.key ? color : isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.12)',
              boxShadow: tone === t.key ? `0 0 8px ${alpha(color, 0.7)}` : 'none',
              transition: 'all 0.2s',
            }} />
            <Box sx={{ flex: 1 }}>
              <Typography sx={{ fontSize: '0.76rem', fontWeight: tone === t.key ? 700 : 500, color: tone === t.key ? color : 'text.primary' }}>{t.label}</Typography>
              <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>{t.desc}</Typography>
            </Box>
            {tone === t.key && <CheckRoundedIcon sx={{ fontSize: 14, color, flexShrink: 0 }} />}
          </Box>
        ))}
      </Cluster>

      {/* Automation level */}
      <Cluster label="Automation Level" labelColor={color} isDark={isDark} theme={theme}>
        {([
          { id: 'off',    label: 'Manual only',   desc: 'AI drafts, you send everything', badge: null },
          { id: 'assist', label: 'AI Assist',      desc: 'AI drafts, you approve before sending', badge: 'Recommended' },
          { id: 'auto',   label: 'Full Autopilot', desc: 'AI sends replies automatically', badge: 'Advanced' },
        ] as const).map((opt, i) => (
          <Box key={opt.id} component="button" onClick={() => { setAutoLevel(opt.id); handleUpdateSetting('automation_level', opt.id); }} sx={{
            display: 'flex', alignItems: 'center', gap: 1.25, width: '100%',
            px: 1.5, py: 0.95, border: 'none', cursor: 'pointer', textAlign: 'left',
            background: autoLevel === opt.id ? alpha(color, isDark ? 0.1 : 0.06) : 'transparent',
            borderBottom: i < 2 ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}` : 'none',
            transition: 'background 0.15s',
            '&:hover': { background: alpha(color, isDark ? 0.07 : 0.04) },
          }}>
            <Box sx={{
              width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
              background: autoLevel === opt.id ? color : isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.12)',
              boxShadow: autoLevel === opt.id ? `0 0 8px ${alpha(color, 0.7)}` : 'none',
              transition: 'all 0.2s',
            }} />
            <Box sx={{ flex: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                <Typography sx={{ fontSize: '0.76rem', fontWeight: autoLevel === opt.id ? 700 : 500, color: autoLevel === opt.id ? color : 'text.primary' }}>{opt.label}</Typography>
                {opt.badge && <GlowChip label={opt.badge} color={color} isDark={isDark} />}
              </Box>
              <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>{opt.desc}</Typography>
            </Box>
            {autoLevel === opt.id && <CheckRoundedIcon sx={{ fontSize: 14, color, flexShrink: 0 }} />}
          </Box>
        ))}
      </Cluster>

      {/* Custom instructions */}
      <Cluster label="Custom Instructions" labelColor={color} isDark={isDark} theme={theme}>
        <Box sx={{ px: 1.5, py: 1.25 }}>
          <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mb: 0.75 }}>
            Tell AI about your business, tone preferences, and what to avoid.
          </Typography>
          <Box sx={{
            borderRadius: '10px', overflow: 'hidden',
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
            background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)',
          }}>
            <InputBase 
              multiline 
              rows={3} 
              value={customInstructions}
              onChange={(e) => setCustomInstructions(e.target.value)}
              placeholder="Tell AI about your business, tone preferences, and what to avoid..."
              sx={{ fontSize: '0.75rem', color: 'text.primary', width: '100%', px: 1.25, py: 0.9, '& textarea': { lineHeight: 1.6 } }}
            />
          </Box>
          <Box sx={{ mt: 1, display: 'flex', justifyContent: 'flex-end' }}>
            <Btn label="Save instructions" color={color} icon={CheckRoundedIcon} isDark={isDark} theme={theme} size="xs" />
          </Box>
        </Box>
      </Cluster>

      {/* Target Audience */}
      <Cluster label="Target Audience" labelColor={color} isDark={isDark} theme={theme}>
        <Box sx={{ px: 1.5, py: 1.25 }}>
          <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mb: 0.75 }}>
            Describe your ideal customer or target audience.
          </Typography>
          <Box sx={{
            borderRadius: '10px', overflow: 'hidden',
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
            background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)',
          }}>
            <InputBase 
              multiline 
              rows={2} 
              value={targetAudience}
              onChange={(e) => setTargetAudience(e.target.value)}
              placeholder="e.g., B2B SaaS companies, mid-market enterprises, tech startups..."
              sx={{ fontSize: '0.75rem', color: 'text.primary', width: '100%', px: 1.25, py: 0.9, '& textarea': { lineHeight: 1.6 } }}
            />
          </Box>
        </Box>
      </Cluster>

      {/* Use Cases */}
      <Cluster label="Use Cases" labelColor={color} isDark={isDark} theme={theme}>
        <Box sx={{ px: 1.5, py: 1.25 }}>
          <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mb: 0.75 }}>
            How you plan to use AI for your business.
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
            {USE_CASES.map((u) => {
              const active = useCases.includes(u.key);
              return (
                <Box
                  key={u.key}
                  component="button"
                  onClick={() => {
                    const next = active ? useCases.filter(k => k !== u.key) : [...useCases, u.key];
                    setUseCases(next);
                  }}
                  sx={{
                    px: 1.25, py: 0.5, borderRadius: '7px', cursor: 'pointer', border: 'none',
                    border: `1px solid ${active ? color : isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)'}`,
                    background: active ? alpha(color, isDark ? 0.15 : 0.1) : 'transparent',
                    transition: 'all 0.18s ease',
                    '&:hover': { borderColor: color, background: alpha(color, isDark ? 0.1 : 0.06) },
                  }}
                >
                  <Typography sx={{ fontSize: '0.7rem', color: active ? color : 'text.secondary', fontWeight: active ? 600 : 400 }}>
                    {u.label}
                  </Typography>
                </Box>
              );
            })}
          </Box>
        </Box>
      </Cluster>

      <Cluster label="Behavior" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Learn from my edits" hint="AI improves based on how you edit drafts" isDark={isDark} theme={theme}><Switch checked={learnFromEdits} onChange={e => { setLearnFromEdits(e.target.checked); handleUpdateSetting('learn_from_edits', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Personalize per lead" hint="Use lead data to customize each message" isDark={isDark} theme={theme}><Switch checked={personalizePerLead} onChange={e => { setPersonalizePerLead(e.target.checked); handleUpdateSetting('personalize_per_lead', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Avoid repetition" hint="Don't repeat phrases across a sequence" isDark={isDark} theme={theme}><Switch checked={avoidRepetition} onChange={e => { setAvoidRepetition(e.target.checked); handleUpdateSetting('avoid_repetition', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Max reply length" isDark={isDark} theme={theme} last>
          <PillToggle options={[{ id: 'short', label: 'Short' }, { id: 'medium', label: 'Medium' }, { id: 'long', label: 'Long' }]} value={maxReplyLength} onChange={(v) => { setMaxReplyLength(v); handleUpdateSetting('max_reply_length', v); }} color={color} isDark={isDark} theme={theme} />
        </FieldRow>
      </Cluster>
    </Box>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// AUTOMATION
// ══════════════════════════════════════════════════════════════════════════════
function AutomationSection({ isDark, theme, settings, updateSettings }: { isDark: boolean; theme: Theme; settings?: any; updateSettings?: any }) {
  const [rules, setRules] = useState(AUTOMATION_RULES);
  const toggle = (id: string) => setRules(r => r.map(x => x.id === id ? { ...x, enabled: !x.enabled } : x));
  const [delayBetweenSteps, setDelayBetweenSteps] = useState<'1d' | '3d' | '7d'>(settings?.delay_between_steps ?? '3d');
  const [maxEmailsPerLead, setMaxEmailsPerLead] = useState<'3' | '5' | '7'>(String(settings?.max_emails_per_lead ?? 5) as '3' | '5' | '7');
  const [automationEnabled, setAutomationEnabled] = useState(settings?.automation_enabled ?? true);
  const [pauseOnWeekends, setPauseOnWeekends] = useState(settings?.pause_on_weekends ?? true);
  const [respectSendingHours, setRespectSendingHours] = useState(settings?.respect_sending_hours ?? true);
  const [stopOnReply, setStopOnReply] = useState(settings?.stop_on_reply ?? true);
  const color = '#fbbf24';
  const activeCount = rules.filter(r => r.enabled).length;
  
  useEffect(() => {
    if (settings) {
      setDelayBetweenSteps(settings.delay_between_steps ?? '3d');
      setMaxEmailsPerLead(String(settings.max_emails_per_lead ?? 5) as '3' | '5' | '7');
      setAutomationEnabled(settings.automation_enabled ?? true);
      setPauseOnWeekends(settings.pause_on_weekends ?? true);
      setRespectSendingHours(settings.respect_sending_hours ?? true);
      setStopOnReply(settings.stop_on_reply ?? true);
    }
  }, [settings]);
  
  const handleUpdateSetting = async (key: string, value: any) => {
    if (updateSettings) {
      await updateSettings.mutateAsync({ [key]: value });
    }
  };

  return (
    <Box>
      <SectionHead title="Automation" subtitle="Rules, triggers, and sequence settings" color={color} icon={BoltRoundedIcon} isDark={isDark} />

      {/* Stats strip */}
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1, mb: 2.5 }}>
        {[
          { label: 'Active rules', value: activeCount, color },
          { label: 'Triggered today', value: 47, color: '#34d399' },
          { label: 'Emails automated', value: 312, color: '#818cf8' },
        ].map(s => (
          <Box key={s.label} sx={{
            px: 1.25, py: 1, borderRadius: '12px', textAlign: 'center',
            background: isDark ? alpha(s.color, 0.08) : alpha(s.color, 0.05),
            border: `1px solid ${alpha(s.color, isDark ? 0.2 : 0.12)}`,
          }}>
            <Typography sx={{ fontSize: '1.3rem', fontWeight: 900, color: s.color, lineHeight: 1, letterSpacing: '-0.04em' }}>
              <CountUp target={s.value} />
            </Typography>
            <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled', mt: 0.2 }}>{s.label}</Typography>
          </Box>
        ))}
      </Box>

      <Cluster label="Global Controls" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Enable automation engine" hint="Master switch for all automation" isDark={isDark} theme={theme}><Switch checked={automationEnabled} onChange={e => { setAutomationEnabled(e.target.checked); handleUpdateSetting('automation_enabled', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Pause on weekends" hint="No automated emails on Sat/Sun" isDark={isDark} theme={theme}><Switch checked={pauseOnWeekends} onChange={e => { setPauseOnWeekends(e.target.checked); handleUpdateSetting('pause_on_weekends', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Respect sending hours" hint="Only send between 9am–6pm local time" isDark={isDark} theme={theme} last><Switch checked={respectSendingHours} onChange={e => { setRespectSendingHours(e.target.checked); handleUpdateSetting('respect_sending_hours', e.target.checked); }} size="small" /></FieldRow>
      </Cluster>

      <Cluster label="Rules" labelColor={color} isDark={isDark} theme={theme}
        action={<Btn label="Add rule" color={color} icon={AddRoundedIcon} isDark={isDark} theme={theme} size="xs" />}
      >
        {rules.map((rule, i) => (
          <Box key={rule.id} sx={{
            display: 'flex', alignItems: 'center', gap: 1.25, px: 1.5, py: 1,
            borderBottom: i < rules.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}` : 'none',
            transition: 'background 0.15s',
            '&:hover': { background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)' },
          }}>
            <Box sx={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0, background: rule.enabled ? color : isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)', boxShadow: rule.enabled ? `0 0 6px ${alpha(color, 0.6)}` : 'none', transition: 'all 0.2s' }} />
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: rule.enabled ? 'text.primary' : 'text.disabled' }}>{rule.name}</Typography>
              <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>{rule.trigger} → {rule.action}</Typography>
            </Box>
            <Switch checked={rule.enabled} onChange={() => toggle(rule.id)} size="small" />
          </Box>
        ))}
      </Cluster>

      <Cluster label="Sequence Defaults" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Delay between steps" isDark={isDark} theme={theme}>
          <PillToggle options={[{ id: '1d', label: '1d' }, { id: '3d', label: '3d' }, { id: '7d', label: '7d' }]} value={delayBetweenSteps} onChange={(v) => { setDelayBetweenSteps(v); handleUpdateSetting('delay_between_steps', v); }} color={color} isDark={isDark} theme={theme} />
        </FieldRow>
        <FieldRow label="Stop on reply" hint="Pause sequence when lead replies" isDark={isDark} theme={theme}><Switch checked={stopOnReply} onChange={e => { setStopOnReply(e.target.checked); handleUpdateSetting('stop_on_reply', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Max emails per lead" isDark={isDark} theme={theme} last>
          <PillToggle options={[{ id: '3', label: '3' }, { id: '5', label: '5' }, { id: '7', label: '7' }]} value={maxEmailsPerLead} onChange={(v) => { setMaxEmailsPerLead(v); handleUpdateSetting('max_emails_per_lead', Number(v)); }} color={color} isDark={isDark} theme={theme} />
        </FieldRow>
      </Cluster>
    </Box>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// NOTIFICATIONS
// ══════════════════════════════════════════════════════════════════════════════
function NotificationsSection({ isDark, theme, settings, updateSettings }: { isDark: boolean; theme: Theme; settings?: any; updateSettings?: any }) {
  const [notifBatching, setNotifBatching] = useState<'instant' | 'hourly' | 'daily'>(settings?.notification_batching ?? 'instant');
  const [emailNewReply, setEmailNewReply] = useState(settings?.email_new_reply ?? true);
  const [emailCampaignComplete, setEmailCampaignComplete] = useState(settings?.email_campaign_complete ?? true);
  const [emailLeadStatus, setEmailLeadStatus] = useState(settings?.email_lead_status ?? false);
  const [emailWeeklyDigest, setEmailWeeklyDigest] = useState(settings?.email_weekly_digest ?? true);
  const [inappRealtimeReplies, setInappRealtimeReplies] = useState(settings?.inapp_realtime_replies ?? true);
  const [inappAiActions, setInappAiActions] = useState(settings?.inapp_ai_actions ?? true);
  const [inappTeamActivity, setInappTeamActivity] = useState(settings?.inapp_team_activity ?? false);
  const [inappSystemAlerts, setInappSystemAlerts] = useState(settings?.inapp_system_alerts ?? true);
  const color = '#f87171';
  
  useEffect(() => {
    if (settings) {
      setNotifBatching(settings.notification_batching ?? 'instant');
      setEmailNewReply(settings.email_new_reply ?? true);
      setEmailCampaignComplete(settings.email_campaign_complete ?? true);
      setEmailLeadStatus(settings.email_lead_status ?? false);
      setEmailWeeklyDigest(settings.email_weekly_digest ?? true);
      setInappRealtimeReplies(settings.inapp_realtime_replies ?? true);
      setInappAiActions(settings.inapp_ai_actions ?? true);
      setInappTeamActivity(settings.inapp_team_activity ?? false);
      setInappSystemAlerts(settings.inapp_system_alerts ?? true);
    }
  }, [settings]);
  
  const handleUpdateSetting = async (key: string, value: any) => {
    if (updateSettings) {
      await updateSettings.mutateAsync({ [key]: value });
    }
  };
  return (
    <Box>
      <SectionHead title="Notifications" subtitle="Alerts, digests, and activity updates" color={color} icon={NotificationsRoundedIcon} isDark={isDark} />
      <Cluster label="Email Alerts" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="New reply received" isDark={isDark} theme={theme}><Switch checked={emailNewReply} onChange={e => { setEmailNewReply(e.target.checked); handleUpdateSetting('email_new_reply', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Campaign completed" isDark={isDark} theme={theme}><Switch checked={emailCampaignComplete} onChange={e => { setEmailCampaignComplete(e.target.checked); handleUpdateSetting('email_campaign_complete', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Lead status changed" isDark={isDark} theme={theme}><Switch checked={emailLeadStatus} onChange={e => { setEmailLeadStatus(e.target.checked); handleUpdateSetting('email_lead_status', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Weekly digest" hint="Summary every Monday morning" isDark={isDark} theme={theme} last><Switch checked={emailWeeklyDigest} onChange={e => { setEmailWeeklyDigest(e.target.checked); handleUpdateSetting('email_weekly_digest', e.target.checked); }} size="small" /></FieldRow>
      </Cluster>
      <Cluster label="In-App Alerts" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Real-time reply alerts" isDark={isDark} theme={theme}><Switch checked={inappRealtimeReplies} onChange={e => { setInappRealtimeReplies(e.target.checked); handleUpdateSetting('inapp_realtime_replies', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="AI action notifications" isDark={isDark} theme={theme}><Switch checked={inappAiActions} onChange={e => { setInappAiActions(e.target.checked); handleUpdateSetting('inapp_ai_actions', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Team activity" isDark={isDark} theme={theme}><Switch checked={inappTeamActivity} onChange={e => { setInappTeamActivity(e.target.checked); handleUpdateSetting('inapp_team_activity', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="System alerts" hint="Downtime, errors, account issues" isDark={isDark} theme={theme} last><Switch checked={inappSystemAlerts} onChange={e => { setInappSystemAlerts(e.target.checked); handleUpdateSetting('inapp_system_alerts', e.target.checked); }} size="small" /></FieldRow>
      </Cluster>
      <Cluster label="Frequency" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Notification batching" isDark={isDark} theme={theme} last>
          <PillToggle options={[{ id: 'instant', label: 'Instant' }, { id: 'hourly', label: 'Hourly' }, { id: 'daily', label: 'Daily' }]} value={notifBatching} onChange={(v) => { setNotifBatching(v); handleUpdateSetting('notification_batching', v); }} color={color} isDark={isDark} theme={theme} />
        </FieldRow>
      </Cluster>
    </Box>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// SECURITY
// ══════════════════════════════════════════════════════════════════════════════
function SecuritySection({ isDark, theme, settings, updateSettings }: { isDark: boolean; theme: Theme; settings?: any; updateSettings?: any }) {
  const [require2FAForTeam, setRequire2FAForTeam] = useState(settings?.require_2fa_for_team ?? false);
  const color = '#fb923c';
  
  useEffect(() => {
    if (settings) {
      setRequire2FAForTeam(settings.require_2fa_for_team ?? false);
    }
  }, [settings]);
  
  const handleUpdateSetting = async (key: string, value: any) => {
    if (updateSettings) {
      await updateSettings.mutateAsync({ [key]: value });
    }
  };
  
  const auditLog = [
    { action: 'Password changed',    time: '2h ago',   ip: '192.168.1.1',  ok: true },
    { action: 'New device login',    time: '1d ago',   ip: '10.0.0.42',    ok: true },
    { action: 'API key generated',   time: '3d ago',   ip: '192.168.1.1',  ok: true },
    { action: 'Failed login attempt',time: '5d ago',   ip: '45.33.32.156', ok: false },
  ];
  return (
    <Box>
      <SectionHead title="Security" subtitle="Access control, API keys, and audit log" color={color} icon={ShieldRoundedIcon} isDark={isDark} />
      <Cluster label="Access Control" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Require 2FA for team" hint="All members must enable 2FA" isDark={isDark} theme={theme}><Switch checked={require2FAForTeam} onChange={e => { setRequire2FAForTeam(e.target.checked); handleUpdateSetting('require_2fa_for_team', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Single sign-on (SSO)" hint="Connect your identity provider" isDark={isDark} theme={theme}>
          <Btn label="Configure" color={color} isDark={isDark} theme={theme} size="xs" />
        </FieldRow>
        <FieldRow label="IP allowlist" hint="Restrict access to specific IPs" isDark={isDark} theme={theme} last>
          <Btn label="Manage" color={color} isDark={isDark} theme={theme} size="xs" />
        </FieldRow>
      </Cluster>

      <Cluster label="API Keys" labelColor={color} isDark={isDark} theme={theme}>
        <Box sx={{ px: 1.5, py: 2, textAlign: 'center' }}>
          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mb: 0.5 }}>
            API Key Management
          </Typography>
          <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', lineHeight: 1.6 }}>
            Coming Soon - Generate and manage API keys for programmatic access
          </Typography>
        </Box>
      </Cluster>

      <Cluster label="Audit Log" labelColor={color} isDark={isDark} theme={theme}>
        {auditLog.map((ev, i) => (
          <Box key={i} sx={{
            display: 'flex', alignItems: 'center', gap: 1.25, px: 1.5, py: 0.9,
            borderBottom: i < auditLog.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}` : 'none',
          }}>
            <Box sx={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0, background: ev.ok ? '#34d399' : '#f87171', boxShadow: `0 0 6px ${alpha(ev.ok ? '#34d399' : '#f87171', 0.6)}` }} />
            <Box sx={{ flex: 1 }}>
              <Typography sx={{ fontSize: '0.74rem', fontWeight: 500, color: 'text.primary' }}>{ev.action}</Typography>
              <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>{ev.ip} · {ev.time}</Typography>
            </Box>
            <GlowChip label={ev.ok ? 'OK' : 'Alert'} color={ev.ok ? '#34d399' : '#f87171'} isDark={isDark} />
          </Box>
        ))}
      </Cluster>
    </Box>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// TEAM
// ══════════════════════════════════════════════════════════════════════════════
function TeamSection({ isDark, theme, settings, updateSettings }: { isDark: boolean; theme: Theme; settings?: any; updateSettings?: any }) {
  const [defaultRole, setDefaultRole] = useState<'viewer' | 'member' | 'admin'>(settings?.default_member_role ?? 'member');
  const [workspaceName, setWorkspaceName] = useState(settings?.workspace_name ?? 'Acme Corp');
  const [inviteByDomain, setInviteByDomain] = useState(settings?.invite_by_domain ?? false);
  const [requireAdminApproval, setRequireAdminApproval] = useState(settings?.require_admin_approval ?? true);
  const color = '#60a5fa';
  
  useEffect(() => {
    if (settings) {
      setDefaultRole(settings.default_member_role ?? 'member');
      setWorkspaceName(settings.workspace_name ?? 'Acme Corp');
      setInviteByDomain(settings.invite_by_domain ?? false);
      setRequireAdminApproval(settings.require_admin_approval ?? true);
    }
  }, [settings]);
  
  const handleUpdateSetting = async (key: string, value: any) => {
    if (updateSettings) {
      await updateSettings.mutateAsync({ [key]: value });
    }
  };
  return (
    <Box>
      <SectionHead title="Team" subtitle="Workspace settings and member controls" color={color} icon={GroupsRoundedIcon} isDark={isDark} />
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1, mb: 2.5 }}>
        {[{ label: 'Members', value: 7, color }, { label: 'Active', value: 5, color: '#34d399' }, { label: 'Pending', value: 2, color: '#fbbf24' }].map(s => (
          <Box key={s.label} sx={{ px: 1.25, py: 1, borderRadius: '12px', textAlign: 'center', background: isDark ? alpha(s.color, 0.08) : alpha(s.color, 0.05), border: `1px solid ${alpha(s.color, isDark ? 0.2 : 0.12)}` }}>
            <Typography sx={{ fontSize: '1.3rem', fontWeight: 900, color: s.color, lineHeight: 1, letterSpacing: '-0.04em' }}><CountUp target={s.value} /></Typography>
            <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled', mt: 0.2 }}>{s.label}</Typography>
          </Box>
        ))}
      </Box>
      <Cluster label="Workspace" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Workspace name" isDark={isDark} theme={theme}><EditField value={workspaceName} onChange={(val) => { setWorkspaceName(val); handleUpdateSetting('workspace_name', val); }} isDark={isDark} theme={theme} /></FieldRow>
        <FieldRow label="Default member role" isDark={isDark} theme={theme} last>
          <PillToggle options={[{ id: 'viewer', label: 'Viewer' }, { id: 'member', label: 'Member' }, { id: 'admin', label: 'Admin' }]} value={defaultRole} onChange={(v) => { setDefaultRole(v); handleUpdateSetting('default_member_role', v); }} color={color} isDark={isDark} theme={theme} />
        </FieldRow>
      </Cluster>
      <Cluster label="Access Policy" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Invite by email domain" hint="Auto-approve @company.com emails" isDark={isDark} theme={theme}><Switch checked={inviteByDomain} onChange={e => { setInviteByDomain(e.target.checked); handleUpdateSetting('invite_by_domain', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Require admin approval" hint="New members need admin sign-off" isDark={isDark} theme={theme} last><Switch checked={requireAdminApproval} onChange={e => { setRequireAdminApproval(e.target.checked); handleUpdateSetting('require_admin_approval', e.target.checked); }} size="small" /></FieldRow>
      </Cluster>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Btn label="Manage full team →" color={color} isDark={isDark} theme={theme} />
      </Box>
    </Box>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// DATA & PRIVACY
// ══════════════════════════════════════════════════════════════════════════════
function DataSection({ isDark, theme, settings, updateSettings }: { isDark: boolean; theme: Theme; settings?: any; updateSettings?: any }) {
  const [deleteModal, setDeleteModal] = useState(false);
  const [analyticsImprovement, setAnalyticsImprovement] = useState(settings?.analytics_improvement ?? true);
  const [personalizationData, setPersonalizationData] = useState(settings?.personalization_data ?? true);
  const [thirdPartyIntegrations, setThirdPartyIntegrations] = useState(settings?.third_party_integrations ?? false);
  const color = '#a3e635';
  
  useEffect(() => {
    if (settings) {
      setAnalyticsImprovement(settings.analytics_improvement ?? true);
      setPersonalizationData(settings.personalization_data ?? true);
      setThirdPartyIntegrations(settings.third_party_integrations ?? false);
    }
  }, [settings]);
  
  const handleUpdateSetting = async (key: string, value: any) => {
    if (updateSettings) {
      await updateSettings.mutateAsync({ [key]: value });
    }
  };
  return (
    <Box>
      <SectionHead title="Data & Privacy" subtitle="Usage, exports, and account deletion" color={color} icon={StorageRoundedIcon} isDark={isDark} />
      <Cluster label="Data Usage" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Analytics & improvement" hint="Help improve AI with anonymized data" isDark={isDark} theme={theme}><Switch checked={analyticsImprovement} onChange={e => { setAnalyticsImprovement(e.target.checked); handleUpdateSetting('analytics_improvement', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Personalization data" hint="Use activity to personalize experience" isDark={isDark} theme={theme}><Switch checked={personalizationData} onChange={e => { setPersonalizationData(e.target.checked); handleUpdateSetting('personalization_data', e.target.checked); }} size="small" /></FieldRow>
        <FieldRow label="Third-party integrations" hint="Share data with connected apps" isDark={isDark} theme={theme} last><Switch checked={thirdPartyIntegrations} onChange={e => { setThirdPartyIntegrations(e.target.checked); handleUpdateSetting('third_party_integrations', e.target.checked); }} size="small" /></FieldRow>
      </Cluster>

      <Cluster label="Export" labelColor={color} isDark={isDark} theme={theme}>
        {[
          { label: 'All leads', desc: 'CSV with all lead data' },
          { label: 'Campaigns', desc: 'Campaign history and stats' },
          { label: 'Email logs', desc: 'Full sending history' },
        ].map((item, i) => (
          <FieldRow key={item.label} label={item.label} hint={item.desc} isDark={isDark} theme={theme} last={i === 2}>
            <Btn label="Export" color={color} icon={DownloadRoundedIcon} isDark={isDark} theme={theme} size="xs" />
          </FieldRow>
        ))}
      </Cluster>

      {/* Danger zone */}
      <Box sx={{
        px: 1.5, py: 1.25, borderRadius: '14px',
        background: isDark ? alpha('#f87171', 0.06) : alpha('#f87171', 0.04),
        border: `1px solid ${alpha('#f87171', isDark ? 0.2 : 0.15)}`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2,
      }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.25 }}>
            <WarningAmberRoundedIcon sx={{ fontSize: 14, color: '#f87171' }} />
            <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: '#f87171' }}>Danger Zone</Typography>
          </Box>
          <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>Permanently delete your account and all data</Typography>
        </Box>
        <Btn label="Delete account" danger icon={DeleteOutlineRoundedIcon} onClick={() => setDeleteModal(true)} isDark={isDark} theme={theme} />
      </Box>

      <Modal open={deleteModal} onClose={() => setDeleteModal(false)}>
        <Box sx={{
          position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
          width: 360, borderRadius: '18px', p: 3, outline: 'none',
          background: isDark ? '#1e293b' : '#fff',
          border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
          boxShadow: `0 24px 64px ${alpha('#000', 0.4)}`,
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
            <WarningAmberRoundedIcon sx={{ color: '#f87171', fontSize: 20 }} />
            <Typography sx={{ fontSize: '0.9rem', fontWeight: 800, color: 'text.primary' }}>Delete account?</Typography>
          </Box>
          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mb: 2.5, lineHeight: 1.7 }}>
            This will permanently delete your account, all campaigns, leads, and email data. This action cannot be undone.
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
            <Btn label="Cancel" isDark={isDark} theme={theme} onClick={() => setDeleteModal(false)} />
            <Btn label="Yes, delete everything" danger isDark={isDark} theme={theme} />
          </Box>
        </Box>
      </Modal>
    </Box>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// ABOUT
// ══════════════════════════════════════════════════════════════════════════════
function AboutSection({ isDark, theme }: { isDark: boolean; theme: Theme }) {
  const grad = isDark ? darkGradients : lightGradients;
  const color = '#94a3b8';
  const links = [
    { label: 'Privacy Policy', href: '#' }, { label: 'Terms of Service', href: '#' },
    { label: 'Cookie Policy', href: '#' }, { label: 'Contact Support', href: '#' },
    { label: 'Documentation', href: '#' }, { label: 'Status Page', href: '#' },
  ];
  return (
    <Box>
      <SectionHead title="About & Legal" subtitle="Platform info, docs, and policies" color={color} icon={InfoRoundedIcon} isDark={isDark} />

      {/* App identity */}
      <Box sx={{
        mb: 2.5, px: 2, py: 1.75, borderRadius: '14px',
        background: isDark ? 'linear-gradient(135deg, rgba(30,41,59,0.7) 0%, rgba(15,23,42,0.5) 100%)' : 'linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(248,250,252,0.7) 100%)',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'}`,
        display: 'flex', alignItems: 'center', gap: 1.75,
      }}>
        <Box sx={{ width: 44, height: 44, borderRadius: '12px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 8px 20px rgba(129,140,248,0.3)', flexShrink: 0 }}>
          <BoltRoundedIcon sx={{ color: '#fff', fontSize: 22 }} />
        </Box>
        <Box sx={{ flex: 1 }}>
          <Typography sx={{ fontSize: '0.95rem', fontWeight: 800, letterSpacing: '-0.02em', color: 'text.primary' }}>
            MailFlow<Box component="span" sx={{ color: 'primary.main' }}>AI</Box>
          </Typography>
          <Typography sx={{ fontSize: '0.63rem', color: 'text.disabled' }}>Version 2.4.1 · Build 20260325 · GPT-4o</Typography>
        </Box>
        <GlowChip label="Up to date" color="#34d399" isDark={isDark} />
      </Box>

      <Cluster label="Platform Info" labelColor={color} isDark={isDark} theme={theme}>
        <FieldRow label="Version" isDark={isDark} theme={theme}><Typography sx={{ fontSize: '0.72rem', color: 'text.disabled', fontFamily: 'monospace' }}>v2.4.1</Typography></FieldRow>
        <FieldRow label="AI model" isDark={isDark} theme={theme}><GlowChip label="GPT-4o" color="#c084fc" isDark={isDark} /></FieldRow>
        <FieldRow label="Data region" isDark={isDark} theme={theme} last><Typography sx={{ fontSize: '0.72rem', color: 'text.disabled' }}>US East (Virginia)</Typography></FieldRow>
      </Cluster>

      <Cluster label="Legal & Support" labelColor={color} isDark={isDark} theme={theme}>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', p: 0.5, gap: 0.5 }}>
          {links.map(link => (
            <Box key={link.label} component="a" href={link.href} sx={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              px: 1.1, py: 0.85, borderRadius: '9px', textDecoration: 'none',
              border: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}`,
              transition: 'all 0.15s ease',
              '&:hover': { background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)', borderColor: isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)', transform: 'translateY(-1px)' },
            }}>
              <Typography sx={{ fontSize: '0.72rem', fontWeight: 500, color: 'text.secondary' }}>{link.label}</Typography>
              <OpenInNewRoundedIcon sx={{ fontSize: 11, color: 'text.disabled' }} />
            </Box>
          ))}
        </Box>
      </Cluster>
    </Box>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ══════════════════════════════════════════════════════════════════════════════
export default function SettingsPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [active, setActive] = useState<SettingSection>('profile');
  const [search, setSearch] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);
  const grad = isDark ? darkGradients : lightGradients;

  // Fetch settings data with React Query
  const { data: settings, isLoading: settingsLoading, error: settingsError } = useUserSettings();
  const updateSettingsMutation = useUpdateSettings();

  const filtered = NAV_ITEMS.filter(n =>
    !search || n.label.toLowerCase().includes(search.toLowerCase()) || n.description.toLowerCase().includes(search.toLowerCase())
  );

  const activeItem = NAV_ITEMS.find(n => n.id === active)!;

  // Show loading state while fetching settings
  if (settingsLoading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  // Show error state if settings fetch failed
  if (settingsError) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', px: 3 }}>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h6" color="error" gutterBottom>
            Failed to load settings
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {settingsError.message || 'Please try refreshing the page'}
          </Typography>
        </Box>
      </Box>
    );
  }

  const SECTION_MAP: Record<SettingSection, React.ReactNode> = {
    profile:       <ProfileSection isDark={isDark} theme={theme} />,
    account:       <AccountSection isDark={isDark} theme={theme} settings={settings} updateSettings={updateSettingsMutation} />,
    email:         <EmailSection isDark={isDark} theme={theme} settings={settings} updateSettings={updateSettingsMutation} />,
    ai:            <AISection isDark={isDark} theme={theme} settings={settings} updateSettings={updateSettingsMutation} />,
    automation:    <AutomationSection isDark={isDark} theme={theme} settings={settings} updateSettings={updateSettingsMutation} />,
    notifications: <NotificationsSection isDark={isDark} theme={theme} settings={settings} updateSettings={updateSettingsMutation} />,
    security:      <SecuritySection isDark={isDark} theme={theme} settings={settings} updateSettings={updateSettingsMutation} />,
    team:          <TeamSection isDark={isDark} theme={theme} settings={settings} updateSettings={updateSettingsMutation} />,
    data:          <DataSection isDark={isDark} theme={theme} settings={settings} updateSettings={updateSettingsMutation} />,
    about:         <AboutSection isDark={isDark} theme={theme} />,
  };

  // ── Left nav ──────────────────────────────────────────────────────────────
  const NavContent = (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Search */}
      <Box sx={{ px: 1.25, pt: 1.5, pb: 1 }}>
        <Box sx={{
          display: 'flex', alignItems: 'center', gap: 0.75,
          px: 1.1, py: 0.6, borderRadius: '10px',
          background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
          border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
        }}>
          <SearchRoundedIcon sx={{ fontSize: 13, color: 'text.disabled', flexShrink: 0 }} />
          <InputBase value={search} onChange={e => setSearch(e.target.value)} placeholder="Search…"
            sx={{ fontSize: '0.73rem', color: 'text.primary', flex: 1, '& input::placeholder': { color: theme.palette.text.disabled } }}
          />
          {search && (
            <Box component="button" onClick={() => setSearch('')} sx={{ border: 'none', background: 'none', cursor: 'pointer', display: 'flex', p: 0, color: theme.palette.text.disabled }}>
              <CloseRoundedIcon sx={{ fontSize: 12 }} />
            </Box>
          )}
        </Box>
      </Box>

      {/* Nav items */}
      <Box sx={{ flex: 1, px: 1.25, pb: 1.5, overflowY: 'auto',
        '&::-webkit-scrollbar': { width: 3 },
        '&::-webkit-scrollbar-thumb': { background: 'rgba(255,255,255,0.08)', borderRadius: 2 },
      }}>
        {filtered.map(item => {
          const Icon = ICON_MAP[item.icon];
          const isAct = active === item.id;
          return (
            <Box key={item.id} onClick={() => { setActive(item.id); setMobileOpen(false); }} sx={{
              display: 'flex', alignItems: 'center', gap: 1.1,
              px: 1.1, py: 0.8, borderRadius: '10px', cursor: 'pointer', mb: 0.2,
              position: 'relative', overflow: 'hidden',
              background: isAct
                ? isDark ? alpha(item.color, 0.13) : alpha(item.color, 0.09)
                : 'transparent',
              transition: 'all 0.15s ease',
              '&:hover': {
                background: isAct
                  ? isDark ? alpha(item.color, 0.18) : alpha(item.color, 0.12)
                  : isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
              },
              // glow line on left
              '&::before': isAct ? {
                content: '""', position: 'absolute', left: 0, top: '15%', bottom: '15%',
                width: 3, borderRadius: '0 3px 3px 0', background: item.color,
                boxShadow: `0 0 8px ${alpha(item.color, 0.7)}`,
              } : {},
            }}>
              <Box sx={{
                width: 26, height: 26, borderRadius: '8px', flexShrink: 0,
                background: isAct ? alpha(item.color, isDark ? 0.22 : 0.14) : isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.15s',
                boxShadow: isAct ? `0 0 10px ${alpha(item.color, 0.3)}` : 'none',
              }}>
                <Icon sx={{ fontSize: 13, color: isAct ? item.color : 'text.secondary', transition: 'color 0.15s' }} />
              </Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ fontSize: '0.76rem', fontWeight: isAct ? 700 : 500, color: isAct ? item.color : 'text.secondary', lineHeight: 1, transition: 'color 0.15s' }}>
                  {item.label}
                </Typography>
              </Box>
            </Box>
          );
        })}
      </Box>
    </Box>
  );

  return (
    <Box sx={{
      flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0,
    }}>
      {/* ── Slim top bar ── */}
      <Box sx={{
        px: { xs: 2, sm: 2.5 }, py: 1.1, flexShrink: 0,
        borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
        display: 'flex', alignItems: 'center', gap: 1.25,
        background: isDark ? 'rgba(8,13,24,0.85)' : theme.palette.background.paper,
        backdropFilter: 'blur(12px)',
      }}>
        {/* Mobile toggle */}
        <IconButton size="small" onClick={() => setMobileOpen(v => !v)}
          sx={{ display: { xs: 'flex', md: 'none' }, color: 'text.secondary', p: 0.5 }}>
          <MenuRoundedIcon sx={{ fontSize: 17 }} />
        </IconButton>

        {/* Active section icon + name */}
        <Box sx={{
          display: 'flex', alignItems: 'center', gap: 0.75,
          px: 0.9, py: 0.4, borderRadius: '9px',
          background: alpha(activeItem.color, isDark ? 0.12 : 0.08),
          border: `1px solid ${alpha(activeItem.color, isDark ? 0.25 : 0.15)}`,
        }}>
          {(() => { const Icon = ICON_MAP[activeItem.icon]; return <Icon sx={{ fontSize: 13, color: activeItem.color }} />; })()}
          <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: activeItem.color }}>{activeItem.label}</Typography>
        </Box>

        <ChevronRightRoundedIcon sx={{ fontSize: 13, color: 'text.disabled', display: { xs: 'none', sm: 'block' } }} />
        <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', display: { xs: 'none', sm: 'block' } }}>{activeItem.description}</Typography>

        {/* Keyboard shortcut hint */}
        <Box sx={{ ml: 'auto', display: { xs: 'none', lg: 'flex' }, alignItems: 'center', gap: 0.5 }}>
          {['⌘', 'K'].map(k => (
            <Box key={k} sx={{ px: 0.6, py: 0.2, borderRadius: '5px', background: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)', border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}` }}>
              <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: 'text.disabled', fontFamily: 'monospace' }}>{k}</Typography>
            </Box>
          ))}
          <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', ml: 0.25 }}>to search</Typography>
        </Box>
      </Box>

      {/* ── Body ── */}
      <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0, position: 'relative' }}>

        {/* Mobile overlay */}
        {mobileOpen && (
          <Box sx={{
            position: 'absolute', inset: 0, zIndex: 30,
            background: isDark ? 'rgba(8,13,24,0.97)' : 'rgba(248,250,252,0.98)',
            backdropFilter: 'blur(12px)',
            display: { xs: 'flex', md: 'none' }, flexDirection: 'column',
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 2, py: 1.25, borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}` }}>
              <Typography sx={{ fontSize: '0.8rem', fontWeight: 700, color: 'text.primary' }}>Settings</Typography>
              <IconButton size="small" onClick={() => setMobileOpen(false)} sx={{ color: 'text.secondary', p: 0.5 }}>
                <CloseRoundedIcon sx={{ fontSize: 15 }} />
              </IconButton>
            </Box>
            {NavContent}
          </Box>
        )}

        {/* Desktop sidebar */}
        <Box sx={{
          display: { xs: 'none', md: 'flex' }, flexDirection: 'column',
          width: 200, flexShrink: 0,
          borderRight: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
          background: isDark
            ? 'linear-gradient(180deg, rgba(15,10,40,0.7) 0%, rgba(8,13,24,0.5) 100%)'
            : 'linear-gradient(180deg, rgba(255,255,255,0.8) 0%, rgba(248,250,252,0.6) 100%)',
          backdropFilter: 'blur(16px)',
          height: '100%',
        }}>
          {NavContent}
        </Box>

        {/* Content */}
        <Box sx={{
          flex: 1, overflowY: 'auto', minWidth: 0,
          '&::-webkit-scrollbar': { width: 4 },
          '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.18), borderRadius: 2 },
        }}>
          <Box sx={{
            maxWidth: 640, mx: 'auto', px: { xs: 2, sm: 3 }, pt: 2.5, pb: 5,
            animation: 'fadeIn 0.2s ease-out',
            '@keyframes fadeIn': { from: { opacity: 0, transform: 'translateY(6px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
          }}>
            {SECTION_MAP[active]}
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
