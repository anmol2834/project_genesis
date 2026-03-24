'use client';

import { useState, useEffect, useRef } from 'react';
import {
  Box, Typography, useTheme, alpha, InputBase, IconButton, Tooltip, Button, type Theme,
} from '@mui/material';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded';
import PauseRoundedIcon from '@mui/icons-material/PauseRounded';
import EditRoundedIcon from '@mui/icons-material/EditRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import BarChartRoundedIcon from '@mui/icons-material/BarChartRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import ReplyRoundedIcon from '@mui/icons-material/ReplyRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import { CAMPAIGNS, STATUS_CONFIG, Campaign, CampaignStatus } from './campaignData';
import { lightGradients, darkGradients } from '@/theme/palette';

// ── Animated counter ──────────────────────────────────────────────────────────
function CountUp({ target, suffix = '' }: { target: number; suffix?: string }) {
  const [val, setVal] = useState(0);
  const frame = useRef<number | null>(null);
  useEffect(() => {
    const start = performance.now();
    const dur = 1200;
    const tick = (now: number) => {
      const p = Math.min((now - start) / dur, 1);
      setVal(Math.round((1 - Math.pow(1 - p, 3)) * target));
      if (p < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => { if (frame.current) cancelAnimationFrame(frame.current); };
  }, [target]);
  return <>{val.toLocaleString()}{suffix}</>;
}

// ── Progress bar ──────────────────────────────────────────────────────────────
function ProgressBar({ value, color, isDark }: { value: number; color: string; isDark: boolean }) {
  return (
    <Box sx={{
      height: 4, borderRadius: 2,
      background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)',
      overflow: 'hidden',
    }}>
      <Box sx={{
        height: '100%', borderRadius: 2,
        width: `${Math.min(value, 100)}%`,
        background: `linear-gradient(90deg, ${color}, ${alpha(color, 0.6)})`,
        transition: 'width 1s cubic-bezier(0.4,0,0.2,1)',
      }} />
    </Box>
  );
}

// ── Status dot ────────────────────────────────────────────────────────────────
function StatusBadge({ status, isDark }: { status: CampaignStatus; isDark: boolean }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.45,
      px: 0.75, py: 0.25, borderRadius: '6px',
      background: isDark ? cfg.darkBg : cfg.bg,
      border: `1px solid ${alpha(cfg.color, 0.3)}`,
    }}>
      <Box sx={{
        width: 5, height: 5, borderRadius: '50%',
        background: cfg.color,
        boxShadow: status === 'running' ? `0 0 6px ${cfg.color}` : 'none',
        animation: status === 'running' ? 'pulse 2s ease-in-out infinite' : 'none',
        '@keyframes pulse': {
          '0%,100%': { opacity: 1 },
          '50%': { opacity: 0.4 },
        },
      }} />
      <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: cfg.color, letterSpacing: '0.04em' }}>
        {cfg.label}
      </Typography>
    </Box>
  );
}

// ── Campaign card ─────────────────────────────────────────────────────────────
function CampaignCard({ campaign, isDark, theme }: {
  campaign: Campaign;
  isDark: boolean;
  theme: Theme;
}) {
  const progress = campaign.emailsTotal > 0
    ? Math.round((campaign.emailsSent / campaign.emailsTotal) * 100)
    : 0;

  const InsightIcon = campaign.insightType === 'positive'
    ? TrendingUpRoundedIcon
    : campaign.insightType === 'warning'
      ? WarningAmberRoundedIcon
      : AutoAwesomeRoundedIcon;

  const insightColor = campaign.insightType === 'positive'
    ? '#34d399'
    : campaign.insightType === 'warning'
      ? '#fbbf24'
      : '#c084fc';

  return (
    <Box sx={{
      borderRadius: '14px',
      border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
      background: isDark
        ? `linear-gradient(145deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.02) 100%)`
        : theme.palette.background.paper,
      position: 'relative', overflow: 'hidden',
      transition: 'transform 0.2s ease, box-shadow 0.2s ease',
      cursor: 'default',
      '&:hover': {
        transform: 'translateY(-3px)',
        boxShadow: isDark
          ? `0 16px 40px rgba(0,0,0,0.45), 0 0 0 1px ${alpha(campaign.accentColor, 0.25)}`
          : `0 16px 40px rgba(15,23,42,0.1), 0 0 0 1px ${alpha(campaign.accentColor, 0.2)}`,
      },
      '&::before': {
        content: '""', position: 'absolute',
        top: 0, left: 0, right: 0, height: '2.5px',
        background: `linear-gradient(90deg, ${campaign.accentColor}, ${alpha(campaign.accentColor, 0.2)})`,
      },
      animation: 'cardIn 0.3s ease-out both',
      '@keyframes cardIn': {
        from: { opacity: 0, transform: 'translateY(10px)' },
        to:   { opacity: 1, transform: 'translateY(0)' },
      },
    }}>
      <Box sx={{ p: { xs: 1.75, sm: 2 } }}>

        {/* Top row: name + status + actions */}
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1.25 }}>
          <Box sx={{ flex: 1, minWidth: 0, mr: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.5, flexWrap: 'wrap' }}>
              <StatusBadge status={campaign.status} isDark={isDark} />
              {campaign.tags.map((tag) => (
                <Box key={tag} sx={{
                  px: 0.6, py: 0.15, borderRadius: '5px',
                  background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05),
                  border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
                }}>
                  <Typography sx={{ fontSize: '0.52rem', fontWeight: 600, color: 'text.disabled' }}>
                    {tag}
                  </Typography>
                </Box>
              ))}
            </Box>
            <Typography sx={{
              fontSize: { xs: '0.88rem', sm: '0.92rem' },
              fontWeight: 700, color: 'text.primary',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              letterSpacing: '-0.01em',
            }}>
              {campaign.name}
            </Typography>
            <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', mt: 0.2 }}>
              Created {campaign.createdAt} · Last active {campaign.lastActivity}
            </Typography>
          </Box>

          {/* Quick actions */}
          <Box sx={{ display: 'flex', gap: 0.25, flexShrink: 0 }}>
            {campaign.status === 'running' && (
              <Tooltip title="Pause" placement="top">
                <IconButton size="small" sx={{ width: 28, height: 28, borderRadius: '7px', color: '#fbbf24',
                  '&:hover': { background: 'rgba(251,191,36,0.12)' } }}>
                  <PauseRoundedIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Tooltip>
            )}
            {(campaign.status === 'paused' || campaign.status === 'draft') && (
              <Tooltip title="Resume" placement="top">
                <IconButton size="small" sx={{ width: 28, height: 28, borderRadius: '7px', color: '#34d399',
                  '&:hover': { background: 'rgba(52,211,153,0.12)' } }}>
                  <PlayArrowRoundedIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title="Analytics" placement="top">
              <IconButton size="small" sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary',
                '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) } }}>
                <BarChartRoundedIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
            <Tooltip title="Edit" placement="top">
              <IconButton size="small" sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary',
                '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) } }}>
                <EditRoundedIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete" placement="top">
              <IconButton size="small" sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary',
                '&:hover': { background: 'rgba(239,68,68,0.1)', color: '#ef4444' } }}>
                <DeleteOutlineRoundedIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Progress */}
        {campaign.status !== 'draft' && (
          <Box sx={{ mb: 1.5 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>
                {campaign.emailsSent.toLocaleString()} / {campaign.emailsTotal.toLocaleString()} emails
              </Typography>
              <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: campaign.accentColor }}>
                {progress}%
              </Typography>
            </Box>
            <ProgressBar value={progress} color={campaign.accentColor} isDark={isDark} />
          </Box>
        )}

        {/* Stats row */}
        <Box sx={{
          display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 1, mb: 1.5,
        }}>
          {[
            { label: 'Sent',      value: campaign.emailsSent, icon: EmailRoundedIcon,  color: '#818cf8', suffix: '' },
            { label: 'Open Rate', value: campaign.openRate,   icon: BarChartRoundedIcon, color: '#22d3ee', suffix: '%' },
            { label: 'Reply Rate',value: campaign.replyRate,  icon: ReplyRoundedIcon,  color: '#34d399', suffix: '%' },
          ].map(({ label, value, icon: Icon, color, suffix }) => (
            <Box key={label} sx={{
              p: 1, borderRadius: '10px', textAlign: 'center',
              background: isDark ? 'rgba(255,255,255,0.04)' : alpha(theme.palette.text.primary, 0.03),
              border: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
            }}>
              <Icon sx={{ fontSize: 13, color, mb: 0.3 }} />
              <Typography sx={{ fontSize: { xs: '0.9rem', sm: '1rem' }, fontWeight: 800, color: 'text.primary', lineHeight: 1, letterSpacing: '-0.02em' }}>
                {value > 0 ? <CountUp target={value} suffix={suffix} /> : <span>—</span>}
              </Typography>
              <Typography sx={{ fontSize: '0.55rem', color: 'text.disabled', mt: 0.2, fontWeight: 500 }}>
                {label}
              </Typography>
            </Box>
          ))}
        </Box>

        {/* AI Insight */}
        <Box sx={{
          display: 'flex', alignItems: 'flex-start', gap: 0.75,
          px: 1, py: 0.75, borderRadius: '9px',
          background: isDark ? alpha(insightColor, 0.07) : alpha(insightColor, 0.05),
          border: `1px solid ${alpha(insightColor, isDark ? 0.18 : 0.15)}`,
        }}>
          <InsightIcon sx={{ fontSize: 12, color: insightColor, mt: 0.15, flexShrink: 0 }} />
          <Typography sx={{ fontSize: '0.67rem', color: isDark ? alpha(insightColor, 0.9) : insightColor, lineHeight: 1.45, fontWeight: 500 }}>
            {campaign.aiInsight}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────
function EmptyState({ isDark, grad }: { isDark: boolean; grad: string }) {
  return (
    <Box sx={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', py: 10, gap: 2,
      animation: 'fadeIn 0.4s ease-out',
      '@keyframes fadeIn': { from: { opacity: 0 }, to: { opacity: 1 } },
    }}>
      <Box sx={{
        width: 72, height: 72, borderRadius: '20px',
        background: isDark ? 'rgba(129,140,248,0.12)' : 'rgba(67,56,202,0.07)',
        border: `1px solid ${isDark ? 'rgba(129,140,248,0.2)' : 'rgba(67,56,202,0.15)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <CampaignRoundedIcon sx={{ fontSize: 32, color: isDark ? '#818cf8' : '#4338ca' }} />
      </Box>
      <Box sx={{ textAlign: 'center' }}>
        <Typography sx={{ fontSize: '1rem', fontWeight: 700, color: 'text.primary', mb: 0.5 }}>
          No campaigns yet
        </Typography>
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
          Launch your first campaign and start reaching leads at scale.
        </Typography>
      </Box>
      <Button
        startIcon={<AddRoundedIcon />}
        sx={{
          background: grad, color: '#fff', fontWeight: 700,
          fontSize: '0.78rem', px: 2.5, py: 0.9, borderRadius: '10px',
          textTransform: 'none',
          '&:hover': { opacity: 0.88 },
        }}
      >
        Create Campaign
      </Button>
    </Box>
  );
}

// ── Filter tabs ───────────────────────────────────────────────────────────────
const FILTERS: { id: 'all' | CampaignStatus; label: string }[] = [
  { id: 'all',     label: 'All' },
  { id: 'running', label: 'Running' },
  { id: 'paused',  label: 'Paused' },
  { id: 'draft',   label: 'Drafts' },
];

// ── Summary stats ─────────────────────────────────────────────────────────────
function SummaryStats({ campaigns, isDark, theme }: {
  campaigns: Campaign[];
  isDark: boolean;
  theme: Theme;
}) {
  const active    = campaigns.filter(c => c.status === 'running').length;
  const paused    = campaigns.filter(c => c.status === 'paused').length;
  const totalSent = campaigns.reduce((a, c) => a + c.emailsSent, 0);
  const avgReply  = campaigns.filter(c => c.replyRate > 0).length > 0
    ? Math.round(campaigns.filter(c => c.replyRate > 0).reduce((a, c) => a + c.replyRate, 0) / campaigns.filter(c => c.replyRate > 0).length)
    : 0;

  const stats = [
    { label: 'Active',        value: active,    suffix: '',  icon: PlayArrowRoundedIcon, color: '#34d399', darkBg: 'rgba(52,211,153,0.12)',  lightBg: 'rgba(52,211,153,0.07)'  },
    { label: 'Paused',        value: paused,    suffix: '',  icon: PauseRoundedIcon,     color: '#fbbf24', darkBg: 'rgba(251,191,36,0.12)',  lightBg: 'rgba(251,191,36,0.07)'  },
    { label: 'Emails Sent',   value: totalSent, suffix: '',  icon: EmailRoundedIcon,     color: '#22d3ee', darkBg: 'rgba(34,211,238,0.12)',  lightBg: 'rgba(34,211,238,0.07)'  },
    { label: 'Avg Reply Rate',value: avgReply,  suffix: '%', icon: ReplyRoundedIcon,     color: '#c084fc', darkBg: 'rgba(192,132,252,0.12)', lightBg: 'rgba(192,132,252,0.07)' },
  ];

  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', lg: 'repeat(4, 1fr)' }, gap: 1.5 }}>
      {stats.map((s, i) => {
        const Icon = s.icon;
        return (
          <Box key={s.label} sx={{
            p: { xs: 1.5, sm: 2 }, borderRadius: '14px',
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
            background: isDark ? s.darkBg : s.lightBg,
            position: 'relative', overflow: 'hidden',
            transition: 'transform 0.2s ease, box-shadow 0.2s ease',
            '&:hover': { transform: 'translateY(-2px)', boxShadow: isDark ? '0 12px 32px rgba(0,0,0,0.35)' : '0 12px 32px rgba(15,23,42,0.08)' },
            '&::before': {
              content: '""', position: 'absolute', top: 0, left: 0, right: 0, height: '2px',
              background: `linear-gradient(90deg, ${s.color}, ${alpha(s.color, 0.2)})`,
            },
            animation: `cardIn 0.3s ease-out ${i * 0.06}s both`,
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.25 }}>
              <Box sx={{
                width: 32, height: 32, borderRadius: '9px',
                background: alpha(s.color, isDark ? 0.2 : 0.15),
                border: `1px solid ${alpha(s.color, 0.25)}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon sx={{ fontSize: 16, color: s.color }} />
              </Box>
            </Box>
            <Typography sx={{ fontSize: { xs: '1.4rem', sm: '1.6rem' }, fontWeight: 800, letterSpacing: '-0.04em', lineHeight: 1, color: 'text.primary' }}>
              <CountUp target={s.value} suffix={s.suffix} />
            </Typography>
            <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, mt: 0.4, color: 'text.secondary' }}>
              {s.label}
            </Typography>
          </Box>
        );
      })}
    </Box>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function CampaignsPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients.primary : lightGradients.primary;
  const [filter, setFilter] = useState<'all' | CampaignStatus>('all');
  const [search, setSearch] = useState('');

  const filtered = CAMPAIGNS.filter((c) => {
    if (filter !== 'all' && c.status !== filter) return false;
    if (search && !c.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

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
              Campaigns
            </Typography>
            <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mt: 0.3 }}>
              Manage and track all your outreach campaigns
            </Typography>
          </Box>
          <Button
            startIcon={<AddRoundedIcon sx={{ fontSize: '16px !important' }} />}
            sx={{
              background: grad, color: '#fff', fontWeight: 700,
              fontSize: '0.78rem', px: 2, py: 0.85, borderRadius: '10px',
              textTransform: 'none', flexShrink: 0,
              boxShadow: isDark ? '0 4px 20px rgba(129,140,248,0.3)' : '0 4px 20px rgba(67,56,202,0.25)',
              transition: 'all 0.2s ease',
              '&:hover': { opacity: 0.88, transform: 'translateY(-1px)', boxShadow: isDark ? '0 8px 28px rgba(129,140,248,0.4)' : '0 8px 28px rgba(67,56,202,0.35)' },
              '&:active': { transform: 'scale(0.98)' },
            }}
          >
            Create Campaign
          </Button>
        </Box>

        {/* ── Summary stats ── */}
        <SummaryStats campaigns={CAMPAIGNS} isDark={isDark} theme={theme} />

        {/* ── Search + filters ── */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
          {/* Search */}
          <Box sx={{
            display: 'flex', alignItems: 'center', gap: 1,
            px: 1.25, py: 0.75, borderRadius: '10px', flex: { xs: '1 1 100%', sm: '0 0 240px' },
            background: isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04),
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider}`,
          }}>
            <SearchRoundedIcon sx={{ fontSize: 15, color: 'text.disabled', flexShrink: 0 }} />
            <InputBase
              placeholder="Search campaigns..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              sx={{
                fontSize: '0.78rem', color: 'text.primary', flex: 1,
                '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 },
              }}
            />
          </Box>

          {/* Filter tabs */}
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
            {FILTERS.map((f) => {
              const isActive = filter === f.id;
              const count = f.id === 'all' ? CAMPAIGNS.length : CAMPAIGNS.filter(c => c.status === f.id).length;
              return (
                <Box
                  key={f.id}
                  component="button"
                  onClick={() => setFilter(f.id)}
                  sx={{
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
                  }}
                >
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

        {/* ── Campaign grid ── */}
        {filtered.length === 0 ? (
          <EmptyState isDark={isDark} grad={grad} />
        ) : (
          <Box sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', xl: 'repeat(3, 1fr)' },
            gap: 2,
          }}>
            {filtered.map((c) => (
              <CampaignCard key={c.id} campaign={c} isDark={isDark} theme={theme} />
            ))}
          </Box>
        )}
      </Box>
    </Box>
  );
}
