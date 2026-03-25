'use client';

import { useState, useEffect, useRef } from 'react';
import {
  Box, Typography, useTheme, alpha, InputBase, IconButton,
  Tooltip, Button, Modal, type Theme,
} from '@mui/material';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import FileUploadRoundedIcon from '@mui/icons-material/FileUploadRounded';
import EditRoundedIcon from '@mui/icons-material/EditRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import FilterListRoundedIcon from '@mui/icons-material/FilterListRounded';
import KeyboardArrowLeftRoundedIcon from '@mui/icons-material/KeyboardArrowLeftRounded';
import KeyboardArrowRightRoundedIcon from '@mui/icons-material/KeyboardArrowRightRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import LocalFireDepartmentRoundedIcon from '@mui/icons-material/LocalFireDepartmentRounded';
import { LEADS, STATUS_CONFIG, TAG_CONFIG, Lead, LeadStatus, LeadTag } from './leadsData';
import { lightGradients, darkGradients } from '@/theme/palette';
import CSVImportModal from '../shared/CSVImportModal';

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

// ── Score bar ─────────────────────────────────────────────────────────────────
function ScoreBar({ score, isDark }: { score: number; isDark: boolean }) {
  const color = score >= 75 ? '#34d399' : score >= 50 ? '#fbbf24' : '#f87171';
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
      <Box sx={{
        width: 48, height: 4, borderRadius: 2,
        background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)',
        overflow: 'hidden',
      }}>
        <Box sx={{
          height: '100%', borderRadius: 2, width: `${score}%`,
          background: color, transition: 'width 0.8s ease',
        }} />
      </Box>
      <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color, minWidth: 22 }}>
        {score}
      </Typography>
    </Box>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: LeadStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.4,
      px: 0.7, py: 0.2, borderRadius: '6px',
      background: cfg.bg, border: `1px solid ${alpha(cfg.color, 0.3)}`,
    }}>
      <Box sx={{ width: 5, height: 5, borderRadius: '50%', background: cfg.color,
        boxShadow: status === 'engaged' ? `0 0 5px ${cfg.color}` : 'none' }} />
      <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: cfg.color, letterSpacing: '0.04em' }}>
        {cfg.label}
      </Typography>
    </Box>
  );
}

// ── Tag chip ──────────────────────────────────────────────────────────────────
function TagChip({ tag }: { tag: LeadTag }) {
  const cfg = TAG_CONFIG[tag];
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.25,
      px: 0.55, py: 0.1, borderRadius: '4px',
      background: cfg.bg, border: `1px solid ${alpha(cfg.color, 0.25)}`,
    }}>
      {tag === 'hot' && <LocalFireDepartmentRoundedIcon sx={{ fontSize: 8, color: cfg.color }} />}
      <Typography sx={{ fontSize: '0.5rem', fontWeight: 700, color: cfg.color, lineHeight: 1 }}>
        {tag === 'decision-maker' ? 'DM' : tag.charAt(0).toUpperCase() + tag.slice(1)}
      </Typography>
    </Box>
  );
}

// ── Summary stats ─────────────────────────────────────────────────────────────
function SummaryStats({ leads, isDark, theme }: { leads: Lead[]; isDark: boolean; theme: Theme }) {
  const total    = leads.length;
  const engaged  = leads.filter(l => l.status === 'engaged').length;
  const contacted= leads.filter(l => l.status === 'contacted').length;
  const linked   = leads.filter(l => l.campaign !== null).length;

  const stats = [
    { label: 'Total Leads',      value: total,     suffix: '',  icon: PeopleRoundedIcon,     color: '#818cf8', darkBg: 'rgba(129,140,248,0.12)', lightBg: 'rgba(129,140,248,0.07)' },
    { label: 'Engaged',          value: engaged,   suffix: '',  icon: TrendingUpRoundedIcon, color: '#34d399', darkBg: 'rgba(52,211,153,0.12)',  lightBg: 'rgba(52,211,153,0.07)'  },
    { label: 'Contacted',        value: contacted, suffix: '',  icon: BoltRoundedIcon,       color: '#fbbf24', darkBg: 'rgba(251,191,36,0.12)',  lightBg: 'rgba(251,191,36,0.07)'  },
    { label: 'In Campaigns',     value: linked,    suffix: '',  icon: CampaignRoundedIcon,   color: '#c084fc', darkBg: 'rgba(192,132,252,0.12)', lightBg: 'rgba(192,132,252,0.07)' },
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
            '&::before': { content: '""', position: 'absolute', top: 0, left: 0, right: 0, height: '2px', background: `linear-gradient(90deg, ${s.color}, ${alpha(s.color, 0.2)})` },
            animation: `cardIn 0.3s ease-out ${i * 0.06}s both`,
            '@keyframes cardIn': { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
          }}>
            <Box sx={{ width: 32, height: 32, borderRadius: '9px', background: alpha(s.color, isDark ? 0.2 : 0.15), border: `1px solid ${alpha(s.color, 0.25)}`, display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 1.25 }}>
              <Icon sx={{ fontSize: 16, color: s.color }} />
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

// Grid column template — matches header + row cells
// sm: Lead | Status | Score | Actions
// md: + Email + Last Active
// lg: + Tags
// xl: + Campaign
const GRID_COLS = {
  sm: '1fr 90px 80px 90px',
  md: '1fr 160px 90px 80px 80px 90px',
  lg: '1fr 160px 90px 120px 80px 80px 90px',
  xl: '1fr 160px 90px 120px 150px 80px 80px 90px',
};

// ── Desktop table header ──────────────────────────────────────────────────────
function TableHeader({ isDark, theme }: { isDark: boolean; theme: Theme }) {
  return (
    <Box sx={{
      display: 'grid',
      gridTemplateColumns: { sm: GRID_COLS.sm, md: GRID_COLS.md, lg: GRID_COLS.lg, xl: GRID_COLS.xl },
      px: 2, py: 1,
      background: isDark ? 'rgba(255,255,255,0.04)' : alpha(theme.palette.text.primary, 0.03),
      borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
    }}>
      {/* Lead — always */}
      <Box><Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Lead</Typography></Box>
      {/* Email — md+ */}
      <Box sx={{ display: { sm: 'none', md: 'block' } }}><Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Email</Typography></Box>
      {/* Status — always */}
      <Box><Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Status</Typography></Box>
      {/* Tags — lg+ */}
      <Box sx={{ display: { sm: 'none', lg: 'block' } }}><Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Tags</Typography></Box>
      {/* Campaign — xl+ */}
      <Box sx={{ display: { sm: 'none', xl: 'block' } }}><Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Campaign</Typography></Box>
      {/* Score — always */}
      <Box><Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Score</Typography></Box>
      {/* Last Active — md+ */}
      <Box sx={{ display: { sm: 'none', md: 'block' } }}><Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Last Active</Typography></Box>
      {/* Actions — always */}
      <Box />
    </Box>
  );
}

// ── Desktop table row ─────────────────────────────────────────────────────────
function LeadRow({ lead, isDark, theme, index }: { lead: Lead; isDark: boolean; theme: Theme; index: number }) {
  return (
    <Box sx={{
      display: 'grid',
      gridTemplateColumns: { sm: GRID_COLS.sm, md: GRID_COLS.md, lg: GRID_COLS.lg, xl: GRID_COLS.xl },
      alignItems: 'center',
      px: 2, py: 1.25,
      borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : theme.palette.divider}`,
      transition: 'background 0.15s ease',
      '&:hover': { background: isDark ? 'rgba(129,140,248,0.05)' : alpha(theme.palette.primary.main, 0.03) },
      '&:last-child': { borderBottom: 'none' },
      animation: `rowIn 0.25s ease-out ${index * 0.03}s both`,
      '@keyframes rowIn': { from: { opacity: 0, transform: 'translateX(-6px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
    }}>
      {/* Lead name + company */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0, pr: 1 }}>
        <Box sx={{
          width: 34, height: 34, borderRadius: '50%', flexShrink: 0,
          background: alpha(lead.avatarColor, isDark ? 0.22 : 0.12),
          border: `1.5px solid ${alpha(lead.avatarColor, isDark ? 0.4 : 0.25)}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: lead.avatarColor }}>
            {lead.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
          </Typography>
        </Box>
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontSize: '0.82rem', fontWeight: 600, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {lead.name}
          </Typography>
          <Typography sx={{ fontSize: '0.63rem', color: 'text.disabled', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {lead.role} · {lead.company}
          </Typography>
        </Box>
      </Box>

      {/* Email — md+ */}
      <Box sx={{ display: { sm: 'none', md: 'block' }, minWidth: 0, pr: 1 }}>
        <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {lead.email}
        </Typography>
      </Box>

      {/* Status */}
      <Box><StatusBadge status={lead.status} /></Box>

      {/* Tags — lg+ */}
      <Box sx={{ display: { sm: 'none', lg: 'flex' }, gap: 0.4, flexWrap: 'wrap', alignItems: 'center' }}>
        {lead.tags.slice(0, 2).map(t => <TagChip key={t} tag={t} />)}
      </Box>

      {/* Campaign — xl+ */}
      <Box sx={{ display: { sm: 'none', xl: 'block' }, minWidth: 0, pr: 1 }}>
        {lead.campaign
          ? <Typography sx={{ fontSize: '0.67rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{lead.campaign}</Typography>
          : <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>—</Typography>
        }
      </Box>

      {/* Score */}
      <Box><ScoreBar score={lead.score} isDark={isDark} /></Box>

      {/* Last activity — md+ */}
      <Box sx={{ display: { sm: 'none', md: 'block' } }}>
        <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', whiteSpace: 'nowrap' }}>
          {lead.lastActivity}
        </Typography>
      </Box>

      {/* Actions */}
      <Box sx={{ display: 'flex', gap: 0.25, justifyContent: 'flex-end' }}>
        <Tooltip title="Add to Campaign" placement="top">
          <IconButton size="small" sx={{ width: 26, height: 26, borderRadius: '6px', color: 'text.secondary',
            '&:hover': { background: isDark ? 'rgba(129,140,248,0.12)' : alpha(theme.palette.primary.main, 0.08), color: 'primary.main' } }}>
            <CampaignRoundedIcon sx={{ fontSize: 13 }} />
          </IconButton>
        </Tooltip>
        <Tooltip title="Edit" placement="top">
          <IconButton size="small" sx={{ width: 26, height: 26, borderRadius: '6px', color: 'text.secondary',
            '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) } }}>
            <EditRoundedIcon sx={{ fontSize: 13 }} />
          </IconButton>
        </Tooltip>
        <Tooltip title="Delete" placement="top">
          <IconButton size="small" sx={{ width: 26, height: 26, borderRadius: '6px', color: 'text.secondary',
            '&:hover': { background: 'rgba(239,68,68,0.1)', color: '#ef4444' } }}>
            <DeleteOutlineRoundedIcon sx={{ fontSize: 13 }} />
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
}

// ── Mobile lead card ──────────────────────────────────────────────────────────
function LeadCard({ lead, isDark, theme, index }: { lead: Lead; isDark: boolean; theme: Theme; index: number }) {
  return (
    <Box sx={{
      p: 1.5, borderRadius: '12px',
      border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
      background: isDark ? 'rgba(255,255,255,0.03)' : theme.palette.background.paper,
      transition: 'transform 0.18s ease, box-shadow 0.18s ease',
      '&:hover': { transform: 'translateY(-2px)', boxShadow: isDark ? '0 8px 24px rgba(0,0,0,0.3)' : '0 8px 24px rgba(15,23,42,0.08)' },
      animation: `cardIn 0.25s ease-out ${index * 0.04}s both`,
      '@keyframes cardIn': { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
    }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{
            width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
            background: alpha(lead.avatarColor, isDark ? 0.22 : 0.12),
            border: `1.5px solid ${alpha(lead.avatarColor, isDark ? 0.4 : 0.25)}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: lead.avatarColor }}>
              {lead.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
            </Typography>
          </Box>
          <Box>
            <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, color: 'text.primary' }}>{lead.name}</Typography>
            <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>{lead.role} · {lead.company}</Typography>
          </Box>
        </Box>
        <StatusBadge status={lead.status} />
      </Box>

      <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', mb: 0.75 }}>{lead.email}</Typography>

      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', gap: 0.4, flexWrap: 'wrap' }}>
          {lead.tags.slice(0, 2).map(t => <TagChip key={t} tag={t} />)}
        </Box>
        <ScoreBar score={lead.score} isDark={isDark} />
      </Box>

      {lead.campaign && (
        <Box sx={{ mt: 0.75, display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <CampaignRoundedIcon sx={{ fontSize: 11, color: 'text.disabled' }} />
          <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {lead.campaign}
          </Typography>
        </Box>
      )}

      <Box sx={{ display: 'flex', gap: 0.5, mt: 1, justifyContent: 'flex-end' }}>
        <Tooltip title="Add to Campaign"><IconButton size="small" sx={{ width: 26, height: 26, borderRadius: '6px', color: 'text.secondary', '&:hover': { color: 'primary.main', background: isDark ? 'rgba(129,140,248,0.12)' : alpha(theme.palette.primary.main, 0.08) } }}><CampaignRoundedIcon sx={{ fontSize: 13 }} /></IconButton></Tooltip>
        <Tooltip title="Edit"><IconButton size="small" sx={{ width: 26, height: 26, borderRadius: '6px', color: 'text.secondary', '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) } }}><EditRoundedIcon sx={{ fontSize: 13 }} /></IconButton></Tooltip>
        <Tooltip title="Delete"><IconButton size="small" sx={{ width: 26, height: 26, borderRadius: '6px', color: 'text.secondary', '&:hover': { background: 'rgba(239,68,68,0.1)', color: '#ef4444' } }}><DeleteOutlineRoundedIcon sx={{ fontSize: 13 }} /></IconButton></Tooltip>
      </Box>
    </Box>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────
function EmptyState({ isDark, grad, onImport }: { isDark: boolean; grad: string; onImport: () => void }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', py: 10, gap: 2 }}>
      <Box sx={{ width: 72, height: 72, borderRadius: '20px', background: isDark ? 'rgba(129,140,248,0.12)' : 'rgba(67,56,202,0.07)', border: `1px solid ${isDark ? 'rgba(129,140,248,0.2)' : 'rgba(67,56,202,0.15)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <PeopleRoundedIcon sx={{ fontSize: 32, color: isDark ? '#818cf8' : '#4338ca' }} />
      </Box>
      <Box sx={{ textAlign: 'center' }}>
        <Typography sx={{ fontSize: '1rem', fontWeight: 700, color: 'text.primary', mb: 0.5 }}>No leads found</Typography>
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>Import your first leads to start targeting the right people.</Typography>
      </Box>
      <Button onClick={onImport} startIcon={<FileUploadRoundedIcon />} sx={{ background: grad, color: '#fff', fontWeight: 700, fontSize: '0.78rem', px: 2.5, py: 0.9, borderRadius: '10px', textTransform: 'none', '&:hover': { opacity: 0.88 } }}>
        Import Leads
      </Button>
    </Box>
  );
}

const STATUS_FILTERS: { id: 'all' | LeadStatus; label: string }[] = [
  { id: 'all',          label: 'All' },
  { id: 'new',          label: 'New' },
  { id: 'contacted',    label: 'Contacted' },
  { id: 'engaged',      label: 'Engaged' },
  { id: 'unresponsive', label: 'Unresponsive' },
];

const PAGE_SIZE_OPTIONS = [5, 10, 15];

// ── Main page ─────────────────────────────────────────────────────────────────
export default function LeadsPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients.primary : lightGradients.primary;

  const [search, setSearch]         = useState('');
  const [statusFilter, setStatus]   = useState<'all' | LeadStatus>('all');
  const [importOpen, setImportOpen] = useState(false);
  const [page, setPage]             = useState(1);
  const [pageSize, setPageSize]     = useState(10);
  const [showFilters, setShowFilters] = useState(false);

  const filtered = LEADS.filter(l => {
    if (statusFilter !== 'all' && l.status !== statusFilter) return false;
    if (search && !l.name.toLowerCase().includes(search.toLowerCase()) &&
        !l.email.toLowerCase().includes(search.toLowerCase()) &&
        !l.company.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const paginated  = filtered.slice((page - 1) * pageSize, page * pageSize);

  // Reset to page 1 on filter change
  useEffect(() => { setPage(1); }, [search, statusFilter, pageSize]);

  return (
    <Box sx={{ flex: 1, overflowY: 'auto', px: { xs: 2, sm: 3 }, py: { xs: 2, sm: 2.5 },
      '&::-webkit-scrollbar': { width: 4 },
      '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
    }}>
      <Box sx={{ maxWidth: 1200, mx: 'auto', display: 'flex', flexDirection: 'column', gap: 2.5, pb: 4 }}>

        {/* ── Header ── */}
        <Box sx={{ display: 'flex', alignItems: { xs: 'flex-start', sm: 'center' }, justifyContent: 'space-between', flexWrap: 'wrap', gap: 1.5,
          animation: 'fadeDown 0.3s ease-out',
          '@keyframes fadeDown': { from: { opacity: 0, transform: 'translateY(-8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        }}>
          <Box>
            <Typography sx={{ fontSize: { xs: '1.25rem', sm: '1.45rem' }, fontWeight: 800, letterSpacing: '-0.025em', color: 'text.primary', lineHeight: 1.2 }}>
              Leads
            </Typography>
            <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mt: 0.3 }}>
              Manage, filter and target your lead database
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              startIcon={<AddRoundedIcon sx={{ fontSize: '15px !important' }} />}
              onClick={() => setImportOpen(true)}
              sx={{
                background: grad, color: '#fff', fontWeight: 700, fontSize: '0.78rem',
                px: 2, py: 0.85, borderRadius: '10px', textTransform: 'none', flexShrink: 0,
                boxShadow: isDark ? '0 4px 20px rgba(129,140,248,0.3)' : '0 4px 20px rgba(67,56,202,0.25)',
                transition: 'all 0.2s ease',
                '&:hover': { opacity: 0.88, transform: 'translateY(-1px)' },
                '&:active': { transform: 'scale(0.98)' },
              }}
            >
              Import Leads
            </Button>
          </Box>
        </Box>

        {/* ── Stats ── */}
        <SummaryStats leads={LEADS} isDark={isDark} theme={theme} />

        {/* ── Search + filters ── */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
          <Box sx={{
            display: 'flex', alignItems: 'center', gap: 1,
            px: 1.25, py: 0.75, borderRadius: '10px', flex: { xs: '1 1 auto', sm: '0 0 260px' },
            background: isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04),
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider}`,
          }}>
            <SearchRoundedIcon sx={{ fontSize: 15, color: 'text.disabled', flexShrink: 0 }} />
            <InputBase placeholder="Search leads..." value={search} onChange={e => setSearch(e.target.value)}
              sx={{ fontSize: '0.78rem', color: 'text.primary', flex: 1, '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 } }} />
          </Box>

          <Tooltip title="Toggle filters">
            <IconButton size="small" onClick={() => setShowFilters(v => !v)} sx={{
              width: 36, height: 36, borderRadius: '10px', color: showFilters ? 'primary.main' : 'text.secondary',
              border: `1px solid ${showFilters ? (isDark ? 'rgba(129,140,248,0.4)' : alpha(theme.palette.primary.main, 0.3)) : (isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider)}`,
              background: showFilters ? (isDark ? 'rgba(129,140,248,0.12)' : alpha(theme.palette.primary.main, 0.07)) : 'transparent',
            }}>
              <FilterListRoundedIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>

          {showFilters && (
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', animation: 'fadeIn 0.2s ease-out', '@keyframes fadeIn': { from: { opacity: 0 }, to: { opacity: 1 } } }}>
              {STATUS_FILTERS.map(f => {
                const isActive = statusFilter === f.id;
                const count = f.id === 'all' ? LEADS.length : LEADS.filter(l => l.status === f.id).length;
                return (
                  <Box key={f.id} component="button" onClick={() => setStatus(f.id)} sx={{
                    px: 1.1, py: 0.45, borderRadius: '8px', border: 'none', cursor: 'pointer',
                    fontSize: '0.7rem', fontWeight: isActive ? 700 : 500,
                    display: 'flex', alignItems: 'center', gap: 0.5,
                    background: isActive ? (isDark ? 'rgba(129,140,248,0.2)' : alpha(theme.palette.primary.main, 0.1)) : 'transparent',
                    color: isActive ? (isDark ? '#818cf8' : theme.palette.primary.main) : theme.palette.text.secondary,
                    transition: 'all 0.15s ease',
                    '&:hover': { background: isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.05) },
                  }}>
                    {f.label}
                    <Box sx={{ minWidth: 16, height: 16, borderRadius: '5px', px: 0.4, display: 'flex', alignItems: 'center', justifyContent: 'center',
                      background: isActive ? (isDark ? 'rgba(129,140,248,0.3)' : alpha(theme.palette.primary.main, 0.15)) : (isDark ? 'rgba(255,255,255,0.08)' : alpha(theme.palette.text.primary, 0.07)) }}>
                      <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: isActive ? (isDark ? '#818cf8' : theme.palette.primary.main) : 'text.disabled', lineHeight: 1 }}>{count}</Typography>
                    </Box>
                  </Box>
                );
              })}
            </Box>
          )}
        </Box>

        {/* ── Data ── */}
        {filtered.length === 0 ? (
          <EmptyState isDark={isDark} grad={grad} onImport={() => setImportOpen(true)} />
        ) : (
          <>
            {/* Desktop table */}
            <Box sx={{ display: { xs: 'none', sm: 'block' }, borderRadius: '14px', overflow: 'hidden', border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}` }}>
              <TableHeader isDark={isDark} theme={theme} />
              {paginated.map((lead, i) => (
                <LeadRow key={lead.id} lead={lead} isDark={isDark} theme={theme} index={i} />
              ))}
            </Box>

            {/* Mobile cards */}
            <Box sx={{ display: { xs: 'flex', sm: 'none' }, flexDirection: 'column', gap: 1.25 }}>
              {paginated.map((lead, i) => (
                <LeadCard key={lead.id} lead={lead} isDark={isDark} theme={theme} index={i} />
              ))}
            </Box>

            {/* Pagination */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>Rows per page:</Typography>
                <Box sx={{ display: 'flex', gap: 0.4 }}>
                  {PAGE_SIZE_OPTIONS.map(n => (
                    <Box key={n} component="button" onClick={() => setPageSize(n)} sx={{
                      width: 28, height: 24, borderRadius: '6px', border: 'none', cursor: 'pointer',
                      fontSize: '0.68rem', fontWeight: pageSize === n ? 700 : 400,
                      background: pageSize === n ? (isDark ? 'rgba(129,140,248,0.2)' : alpha(theme.palette.primary.main, 0.1)) : 'transparent',
                      color: pageSize === n ? (isDark ? '#818cf8' : theme.palette.primary.main) : theme.palette.text.secondary,
                      transition: 'all 0.15s ease',
                    }}>{n}</Box>
                  ))}
                </Box>
              </Box>

              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>
                  {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, filtered.length)} of {filtered.length}
                </Typography>
                <IconButton size="small" disabled={page === 1} onClick={() => setPage(p => p - 1)} sx={{ width: 28, height: 28, borderRadius: '7px', color: page === 1 ? 'text.disabled' : 'text.secondary', border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider}`, '&:hover:not(:disabled)': { background: isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.05) } }}>
                  <KeyboardArrowLeftRoundedIcon sx={{ fontSize: 16 }} />
                </IconButton>
                {Array.from({ length: totalPages }, (_, i) => i + 1).filter(n => n === 1 || n === totalPages || Math.abs(n - page) <= 1).map((n, i, arr) => (
                  <Box key={n}>
                    {i > 0 && arr[i - 1] !== n - 1 && <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', px: 0.25 }}>…</Typography>}
                    <Box component="button" onClick={() => setPage(n)} sx={{
                      width: 28, height: 28, borderRadius: '7px', border: 'none', cursor: 'pointer',
                      fontSize: '0.7rem', fontWeight: page === n ? 700 : 400,
                      background: page === n ? (isDark ? 'rgba(129,140,248,0.2)' : alpha(theme.palette.primary.main, 0.1)) : 'transparent',
                      color: page === n ? (isDark ? '#818cf8' : theme.palette.primary.main) : theme.palette.text.secondary,
                      transition: 'all 0.15s ease',
                    }}>{n}</Box>
                  </Box>
                ))}
                <IconButton size="small" disabled={page === totalPages} onClick={() => setPage(p => p + 1)} sx={{ width: 28, height: 28, borderRadius: '7px', color: page === totalPages ? 'text.disabled' : 'text.secondary', border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider}`, '&:hover:not(:disabled)': { background: isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.05) } }}>
                  <KeyboardArrowRightRoundedIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Box>
            </Box>
          </>
        )}
      </Box>

      <CSVImportModal open={importOpen} onClose={() => setImportOpen(false)} />
    </Box>
  );
}
