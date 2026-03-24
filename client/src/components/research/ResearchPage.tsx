'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import {
  Box, Typography, useTheme, alpha, InputBase,
  IconButton, Tooltip, Button, Checkbox, type Theme,
} from '@mui/material';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import TuneRoundedIcon from '@mui/icons-material/TuneRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import VerifiedRoundedIcon from '@mui/icons-material/VerifiedRounded';
import BusinessRoundedIcon from '@mui/icons-material/BusinessRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import PhoneRoundedIcon from '@mui/icons-material/PhoneRounded';
import LocationOnRoundedIcon from '@mui/icons-material/LocationOnRounded';
import LanguageRoundedIcon from '@mui/icons-material/LanguageRounded';
import PersonAddRoundedIcon from '@mui/icons-material/PersonAddRounded';
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded';
import BookmarkRoundedIcon from '@mui/icons-material/BookmarkRounded';
import BookmarkBorderRoundedIcon from '@mui/icons-material/BookmarkBorderRounded';
import FilterListRoundedIcon from '@mui/icons-material/FilterListRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import GridViewRoundedIcon from '@mui/icons-material/GridViewRounded';
import TableRowsRoundedIcon from '@mui/icons-material/TableRowsRounded';
import { lightGradients, darkGradients } from '@/theme/palette';
import {
  RESEARCH_RESULTS, RELEVANCE_CONFIG, CONFIDENCE_CONFIG,
  INDUSTRIES, COMPANY_SIZES, getRelevanceLevel,
  ResearchResult, ResearchIndustry,
} from './researchData';

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

// ── Relevance score bar ───────────────────────────────────────────────────────
function ScoreBar({ score, isDark }: { score: number; isDark: boolean }) {
  const level = getRelevanceLevel(score);
  const color = RELEVANCE_CONFIG[level].color;
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
      <Box sx={{
        flex: 1, height: 4, borderRadius: 2,
        background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)',
        overflow: 'hidden',
      }}>
        <Box sx={{
          height: '100%', borderRadius: 2, width: `${score}%`,
          background: `linear-gradient(90deg, ${color}, ${alpha(color, 0.6)})`,
          transition: 'width 0.9s cubic-bezier(0.4,0,0.2,1)',
        }} />
      </Box>
      <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color, minWidth: 24, textAlign: 'right' }}>
        {score}
      </Typography>
    </Box>
  );
}

// ── Relevance badge ───────────────────────────────────────────────────────────
function RelevanceBadge({ score, isDark }: { score: number; isDark: boolean }) {
  const level = getRelevanceLevel(score);
  const cfg = RELEVANCE_CONFIG[level];
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.4,
      px: 0.7, py: 0.2, borderRadius: '6px',
      background: isDark ? cfg.darkBg : cfg.bg,
      border: `1px solid ${alpha(cfg.color, 0.3)}`,
    }}>
      <Box sx={{ width: 5, height: 5, borderRadius: '50%', background: cfg.color, flexShrink: 0,
        boxShadow: level === 'high' ? `0 0 5px ${cfg.color}` : 'none' }} />
      <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: cfg.color, letterSpacing: '0.04em' }}>
        {cfg.label}
      </Typography>
    </Box>
  );
}

// ── Confidence badge ──────────────────────────────────────────────────────────
function ConfidenceBadge({ level }: { level: ResearchResult['confidenceLevel'] }) {
  const cfg = CONFIDENCE_CONFIG[level];
  const Icon = level === 'verified' ? VerifiedRoundedIcon : null;
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.35,
      px: 0.65, py: 0.2, borderRadius: '5px',
      background: cfg.bg, border: `1px solid ${alpha(cfg.color, 0.25)}`,
    }}>
      {Icon && <Icon sx={{ fontSize: 9, color: cfg.color }} />}
      <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: cfg.color, letterSpacing: '0.04em' }}>
        {cfg.label}
      </Typography>
    </Box>
  );
}

// ── Summary stats ─────────────────────────────────────────────────────────────
function SummaryStats({ results, isDark, theme }: {
  results: ResearchResult[]; isDark: boolean; theme: Theme;
}) {
  const total     = results.length;
  const verified  = results.filter(r => r.confidenceLevel === 'verified').length;
  const highMatch = results.filter(r => getRelevanceLevel(r.relevanceScore) === 'high').length;
  const ready     = results.filter(r => r.relevanceScore >= 70 && r.confidenceLevel !== 'unverified').length;

  const stats = [
    { label: 'Results Found',      value: total,     color: '#818cf8', darkBg: 'rgba(129,140,248,0.12)', lightBg: 'rgba(129,140,248,0.07)', Icon: BusinessRoundedIcon },
    { label: 'Verified Contacts',  value: verified,  color: '#34d399', darkBg: 'rgba(52,211,153,0.12)',  lightBg: 'rgba(52,211,153,0.07)',  Icon: CheckCircleRoundedIcon },
    { label: 'High-Quality Leads', value: highMatch, color: '#22d3ee', darkBg: 'rgba(34,211,238,0.12)',  lightBg: 'rgba(34,211,238,0.07)',  Icon: TrendingUpRoundedIcon },
    { label: 'Campaign-Ready',     value: ready,     color: '#c084fc', darkBg: 'rgba(192,132,252,0.12)', lightBg: 'rgba(192,132,252,0.07)', Icon: CampaignRoundedIcon },
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
            <CountUp target={s.value} />
          </Typography>
          <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, mt: 0.4, color: 'text.secondary' }}>{s.label}</Typography>
        </Box>
      ))}
    </Box>
  );
}

// ── Result card (grid view) ───────────────────────────────────────────────────
function ResultCard({ result, isDark, theme, index, selected, onSelect, onToggleSave, onAddToLeads }: {
  result: ResearchResult; isDark: boolean; theme: Theme; index: number;
  selected: boolean; onSelect: (id: string) => void;
  onToggleSave: (id: string) => void; onAddToLeads: (id: string) => void;
}) {
  const level = getRelevanceLevel(result.relevanceScore);
  const accentColor = RELEVANCE_CONFIG[level].color;
  const InsightIcon = result.insightType === 'positive' ? TrendingUpRoundedIcon
    : result.insightType === 'warning' ? WarningAmberRoundedIcon
    : AutoAwesomeRoundedIcon;
  const insightColor = result.insightType === 'positive' ? '#34d399'
    : result.insightType === 'warning' ? '#fbbf24' : '#c084fc';

  return (
    <Box sx={{
      borderRadius: '14px',
      border: `1px solid ${selected
        ? (isDark ? 'rgba(129,140,248,0.45)' : alpha(theme.palette.primary.main, 0.4))
        : (isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider)}`,
      background: selected
        ? isDark ? 'rgba(129,140,248,0.07)' : alpha(theme.palette.primary.main, 0.03)
        : isDark ? 'linear-gradient(145deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02))' : theme.palette.background.paper,
      position: 'relative', overflow: 'hidden',
      transition: 'transform 0.2s ease, box-shadow 0.2s ease, border-color 0.15s ease',
      '&:hover': {
        transform: 'translateY(-3px)',
        boxShadow: isDark
          ? `0 16px 40px rgba(0,0,0,0.4), 0 0 0 1px ${alpha(accentColor, 0.2)}`
          : `0 16px 40px rgba(15,23,42,0.1), 0 0 0 1px ${alpha(accentColor, 0.15)}`,
      },
      '&::before': {
        content: '""', position: 'absolute', top: 0, left: 0, right: 0, height: '2.5px',
        background: `linear-gradient(90deg, ${accentColor}, ${alpha(accentColor, 0.2)})`,
      },
      animation: `cardIn 0.3s ease-out ${index * 0.05}s both`,
      '@keyframes cardIn': { from: { opacity: 0, transform: 'translateY(10px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
    }}>
      <Box sx={{ p: { xs: 1.75, sm: 2 } }}>

        {/* Top row */}
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1.25 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0, flex: 1 }}>
            <Checkbox
              size="small"
              checked={selected}
              onChange={() => onSelect(result.id)}
              sx={{
                p: 0, mr: 0.25, flexShrink: 0,
                color: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(15,23,42,0.2)',
                '&.Mui-checked': { color: isDark ? '#818cf8' : theme.palette.primary.main },
              }}
            />
            {/* Avatar */}
            <Box sx={{
              width: 40, height: 40, borderRadius: '11px', flexShrink: 0,
              background: alpha(result.avatarColor, isDark ? 0.2 : 0.12),
              border: `1.5px solid ${alpha(result.avatarColor, isDark ? 0.35 : 0.22)}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Typography sx={{ fontSize: '0.72rem', fontWeight: 800, color: result.avatarColor }}>
                {result.businessName.slice(0, 2).toUpperCase()}
              </Typography>
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontSize: '0.88rem', fontWeight: 700, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', letterSpacing: '-0.01em' }}>
                {result.businessName}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.2, flexWrap: 'wrap' }}>
                <RelevanceBadge score={result.relevanceScore} isDark={isDark} />
                <ConfidenceBadge level={result.confidenceLevel} />
              </Box>
            </Box>
          </Box>

          {/* Actions */}
          <Box sx={{ display: 'flex', gap: 0.25, flexShrink: 0, ml: 0.5 }}>
            <Tooltip title={result.savedForLater ? 'Saved' : 'Save for later'} placement="top">
              <IconButton size="small" onClick={() => onToggleSave(result.id)} sx={{
                width: 28, height: 28, borderRadius: '7px',
                color: result.savedForLater ? '#fbbf24' : 'text.secondary',
                '&:hover': { background: 'rgba(251,191,36,0.1)', color: '#fbbf24' },
              }}>
                {result.savedForLater
                  ? <BookmarkRoundedIcon sx={{ fontSize: 14 }} />
                  : <BookmarkBorderRoundedIcon sx={{ fontSize: 14 }} />}
              </IconButton>
            </Tooltip>
            <Tooltip title="Add to campaign" placement="top">
              <IconButton size="small" sx={{
                width: 28, height: 28, borderRadius: '7px', color: 'text.secondary',
                '&:hover': { background: isDark ? 'rgba(129,140,248,0.12)' : alpha(theme.palette.primary.main, 0.08), color: isDark ? '#818cf8' : theme.palette.primary.main },
              }}>
                <CampaignRoundedIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
            <Tooltip title={result.addedToLeads ? 'Added to leads' : 'Add to leads'} placement="top">
              <IconButton size="small" onClick={() => onAddToLeads(result.id)} sx={{
                width: 28, height: 28, borderRadius: '7px',
                color: result.addedToLeads ? '#34d399' : 'text.secondary',
                '&:hover': { background: 'rgba(52,211,153,0.1)', color: '#34d399' },
              }}>
                <PersonAddRoundedIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Contact info */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mb: 1.25 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6 }}>
            <PeopleRoundedIcon sx={{ fontSize: 11, color: 'text.disabled', flexShrink: 0 }} />
            <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {result.contactName} · {result.contactRole}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6 }}>
            <EmailRoundedIcon sx={{ fontSize: 11, color: 'text.disabled', flexShrink: 0 }} />
            <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {result.contactEmail}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <LocationOnRoundedIcon sx={{ fontSize: 11, color: 'text.disabled', flexShrink: 0 }} />
              <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled' }}>{result.location}</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <LanguageRoundedIcon sx={{ fontSize: 11, color: 'text.disabled', flexShrink: 0 }} />
              <Typography sx={{ fontSize: '0.68rem', color: isDark ? '#60a5fa' : theme.palette.primary.main }}>
                {result.website}
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* Meta row */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.25, flexWrap: 'wrap' }}>
          <Box sx={{
            px: 0.65, py: 0.2, borderRadius: '5px',
            background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05),
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
          }}>
            <Typography sx={{ fontSize: '0.58rem', fontWeight: 600, color: 'text.secondary' }}>
              {result.industry}
            </Typography>
          </Box>
          <Box sx={{
            px: 0.65, py: 0.2, borderRadius: '5px',
            background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05),
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
          }}>
            <Typography sx={{ fontSize: '0.58rem', fontWeight: 600, color: 'text.secondary' }}>
              {result.companySize} employees
            </Typography>
          </Box>
          {result.phone && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
              <PhoneRoundedIcon sx={{ fontSize: 10, color: 'text.disabled' }} />
              <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>{result.phone}</Typography>
            </Box>
          )}
        </Box>

        {/* Relevance score bar */}
        <Box sx={{ mb: 1.25 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.4 }}>
            <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>AI Relevance Score</Typography>
            <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>Discovered {result.discoveredAt}</Typography>
          </Box>
          <ScoreBar score={result.relevanceScore} isDark={isDark} />
        </Box>

        {/* AI Insight */}
        <Box sx={{
          display: 'flex', alignItems: 'flex-start', gap: 0.75,
          px: 1, py: 0.75, borderRadius: '9px',
          background: isDark ? alpha(insightColor, 0.07) : alpha(insightColor, 0.05),
          border: `1px solid ${alpha(insightColor, isDark ? 0.18 : 0.15)}`,
        }}>
          <InsightIcon sx={{ fontSize: 11, color: insightColor, mt: 0.1, flexShrink: 0 }} />
          <Typography sx={{ fontSize: '0.65rem', color: isDark ? alpha(insightColor, 0.9) : insightColor, lineHeight: 1.45, fontWeight: 500 }}>
            {result.aiInsight}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

// ── Table row (list view) ─────────────────────────────────────────────────────
function ResultRow({ result, isDark, theme, index, selected, onSelect, onToggleSave, onAddToLeads }: {
  result: ResearchResult; isDark: boolean; theme: Theme; index: number;
  selected: boolean; onSelect: (id: string) => void;
  onToggleSave: (id: string) => void; onAddToLeads: (id: string) => void;
}) {
  const level = getRelevanceLevel(result.relevanceScore);
  const accentColor = RELEVANCE_CONFIG[level].color;

  return (
    <Box sx={{
      display: 'grid',
      gridTemplateColumns: '32px 1fr 160px 120px 80px 100px',
      alignItems: 'center', gap: 1.5,
      px: 1.75, py: 1.25,
      borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : theme.palette.divider}`,
      background: selected
        ? isDark ? 'rgba(129,140,248,0.06)' : alpha(theme.palette.primary.main, 0.03)
        : 'transparent',
      transition: 'background 0.15s ease',
      '&:hover': {
        background: selected
          ? isDark ? 'rgba(129,140,248,0.09)' : alpha(theme.palette.primary.main, 0.05)
          : isDark ? 'rgba(255,255,255,0.03)' : alpha(theme.palette.text.primary, 0.02),
      },
      animation: `rowIn 0.25s ease-out ${index * 0.04}s both`,
      '@keyframes rowIn': { from: { opacity: 0, transform: 'translateX(-6px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
    }}>
      {/* Checkbox */}
      <Checkbox size="small" checked={selected} onChange={() => onSelect(result.id)} sx={{
        p: 0, color: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(15,23,42,0.2)',
        '&.Mui-checked': { color: isDark ? '#818cf8' : theme.palette.primary.main },
      }} />

      {/* Business + contact */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0 }}>
        <Box sx={{
          width: 36, height: 36, borderRadius: '9px', flexShrink: 0,
          background: alpha(result.avatarColor, isDark ? 0.2 : 0.12),
          border: `1.5px solid ${alpha(result.avatarColor, isDark ? 0.35 : 0.22)}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Typography sx={{ fontSize: '0.62rem', fontWeight: 800, color: result.avatarColor }}>
            {result.businessName.slice(0, 2).toUpperCase()}
          </Typography>
        </Box>
        <Box sx={{ minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6, mb: 0.15 }}>
            <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {result.businessName}
            </Typography>
            <Box sx={{
              px: 0.55, py: 0.1, borderRadius: '4px', flexShrink: 0,
              background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05),
              border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
            }}>
              <Typography sx={{ fontSize: '0.52rem', fontWeight: 600, color: 'text.disabled' }}>{result.industry}</Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {result.contactName} · {result.contactEmail}
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* Location + size */}
      <Box>
        <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {result.location}
        </Typography>
        <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', mt: 0.1 }}>
          {result.companySize} employees
        </Typography>
      </Box>

      {/* Confidence */}
      <Box><ConfidenceBadge level={result.confidenceLevel} /></Box>

      {/* Score */}
      <Box>
        <Typography sx={{ fontSize: '0.75rem', fontWeight: 800, color: accentColor, letterSpacing: '-0.02em', lineHeight: 1 }}>
          {result.relevanceScore}
        </Typography>
        <Box sx={{ mt: 0.4, height: 3, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)', overflow: 'hidden', width: 48 }}>
          <Box sx={{ height: '100%', borderRadius: 2, width: `${result.relevanceScore}%`, background: accentColor }} />
        </Box>
      </Box>

      {/* Actions */}
      <Box sx={{ display: 'flex', gap: 0.25, justifyContent: 'flex-end' }}>
        <Tooltip title={result.savedForLater ? 'Saved' : 'Save'} placement="top">
          <IconButton size="small" onClick={() => onToggleSave(result.id)} sx={{
            width: 26, height: 26, borderRadius: '6px',
            color: result.savedForLater ? '#fbbf24' : 'text.secondary',
            '&:hover': { background: 'rgba(251,191,36,0.1)', color: '#fbbf24' },
          }}>
            {result.savedForLater ? <BookmarkRoundedIcon sx={{ fontSize: 13 }} /> : <BookmarkBorderRoundedIcon sx={{ fontSize: 13 }} />}
          </IconButton>
        </Tooltip>
        <Tooltip title="Add to campaign" placement="top">
          <IconButton size="small" sx={{
            width: 26, height: 26, borderRadius: '6px', color: 'text.secondary',
            '&:hover': { background: isDark ? 'rgba(129,140,248,0.12)' : alpha(theme.palette.primary.main, 0.08), color: isDark ? '#818cf8' : theme.palette.primary.main },
          }}>
            <CampaignRoundedIcon sx={{ fontSize: 13 }} />
          </IconButton>
        </Tooltip>
        <Tooltip title={result.addedToLeads ? 'Added' : 'Add to leads'} placement="top">
          <IconButton size="small" onClick={() => onAddToLeads(result.id)} sx={{
            width: 26, height: 26, borderRadius: '6px',
            color: result.addedToLeads ? '#34d399' : 'text.secondary',
            '&:hover': { background: 'rgba(52,211,153,0.1)', color: '#34d399' },
          }}>
            <PersonAddRoundedIcon sx={{ fontSize: 13 }} />
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────
function EmptyState({ isDark, grad, onStart }: { isDark: boolean; grad: string; onStart: () => void }) {
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
        '@keyframes float': { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-6px)' } },
      }}>
        <AutoAwesomeRoundedIcon sx={{ fontSize: 36, color: isDark ? '#818cf8' : '#4338ca' }} />
      </Box>
      <Box sx={{ textAlign: 'center' }}>
        <Typography sx={{ fontSize: '1.05rem', fontWeight: 800, color: 'text.primary', mb: 0.5, letterSpacing: '-0.02em' }}>
          No results match your filters
        </Typography>
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', maxWidth: 300 }}>
          Try adjusting your search or filters to discover more business opportunities.
        </Typography>
      </Box>
      <Button onClick={onStart} startIcon={<SearchRoundedIcon />} sx={{
        background: grad, color: '#fff', fontWeight: 700,
        fontSize: '0.78rem', px: 2.5, py: 0.9, borderRadius: '10px',
        textTransform: 'none', boxShadow: '0 4px 20px rgba(99,102,241,0.35)',
        '&:hover': { opacity: 0.88, transform: 'translateY(-1px)' },
      }}>
        Clear Filters
      </Button>
    </Box>
  );
}

// ── Filter panel ──────────────────────────────────────────────────────────────
interface Filters {
  industry: ResearchIndustry | 'all';
  companySize: string;
  relevance: 'all' | 'high' | 'medium' | 'low';
  confidence: 'all' | 'verified' | 'likely' | 'unverified';
}

function FilterPanel({ filters, onChange, isDark, theme, onClose }: {
  filters: Filters; onChange: (f: Filters) => void;
  isDark: boolean; theme: Theme; onClose: () => void;
}) {
  const chipSx = (active: boolean) => ({
    px: 1, py: 0.4, borderRadius: '7px', border: 'none', cursor: 'pointer',
    fontSize: '0.68rem', fontWeight: active ? 700 : 500,
    background: active
      ? isDark ? 'rgba(129,140,248,0.2)' : alpha(theme.palette.primary.main, 0.1)
      : isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04),
    color: active
      ? isDark ? '#818cf8' : theme.palette.primary.main
      : theme.palette.text.secondary,
    border: `1px solid ${active ? (isDark ? 'rgba(129,140,248,0.3)' : alpha(theme.palette.primary.main, 0.25)) : (isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider)}`,
    transition: 'all 0.15s ease',
    '&:hover': { background: isDark ? 'rgba(255,255,255,0.08)' : alpha(theme.palette.text.primary, 0.06) },
  });

  return (
    <Box sx={{
      p: 2, borderRadius: '14px',
      border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider}`,
      background: isDark ? 'rgba(15,10,40,0.7)' : theme.palette.background.paper,
      backdropFilter: 'blur(12px)',
      animation: 'slideDown 0.2s ease-out',
      '@keyframes slideDown': { from: { opacity: 0, transform: 'translateY(-8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
    }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
        <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: 'text.primary' }}>Filters</Typography>
        <IconButton size="small" onClick={onClose} sx={{ width: 24, height: 24, borderRadius: '6px', color: 'text.secondary' }}>
          <CloseRoundedIcon sx={{ fontSize: 13 }} />
        </IconButton>
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' }, gap: 2 }}>
        {/* Industry */}
        <Box>
          <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.08em', mb: 0.75 }}>Industry</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {(['all', ...INDUSTRIES] as const).map((ind) => (
              <Box key={ind} component="button" onClick={() => onChange({ ...filters, industry: ind })} sx={chipSx(filters.industry === ind)}>
                {ind === 'all' ? 'All' : ind}
              </Box>
            ))}
          </Box>
        </Box>

        {/* Company size */}
        <Box>
          <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.08em', mb: 0.75 }}>Company Size</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {(['all', ...COMPANY_SIZES] as const).map((sz) => (
              <Box key={sz} component="button" onClick={() => onChange({ ...filters, companySize: sz })} sx={chipSx(filters.companySize === sz)}>
                {sz === 'all' ? 'All' : sz}
              </Box>
            ))}
          </Box>
        </Box>

        {/* Relevance */}
        <Box>
          <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.08em', mb: 0.75 }}>Relevance</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {(['all', 'high', 'medium', 'low'] as const).map((r) => (
              <Box key={r} component="button" onClick={() => onChange({ ...filters, relevance: r })} sx={chipSx(filters.relevance === r)}>
                {r === 'all' ? 'All' : r.charAt(0).toUpperCase() + r.slice(1)}
              </Box>
            ))}
          </Box>
        </Box>

        {/* Confidence */}
        <Box>
          <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.08em', mb: 0.75 }}>Confidence</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {(['all', 'verified', 'likely', 'unverified'] as const).map((c) => (
              <Box key={c} component="button" onClick={() => onChange({ ...filters, confidence: c })} sx={chipSx(filters.confidence === c)}>
                {c === 'all' ? 'All' : c.charAt(0).toUpperCase() + c.slice(1)}
              </Box>
            ))}
          </Box>
        </Box>
      </Box>
    </Box>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ResearchPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients.primary : lightGradients.primary;

  const [results, setResults] = useState<ResearchResult[]>(RESEARCH_RESULTS);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<'relevance' | 'recent'>('relevance');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    industry: 'all', companySize: 'all', relevance: 'all', confidence: 'all',
  });

  const filtered = useMemo(() => {
    let list = results.filter((r) => {
      if (filters.industry !== 'all' && r.industry !== filters.industry) return false;
      if (filters.companySize !== 'all' && r.companySize !== filters.companySize) return false;
      if (filters.relevance !== 'all' && getRelevanceLevel(r.relevanceScore) !== filters.relevance) return false;
      if (filters.confidence !== 'all' && r.confidenceLevel !== filters.confidence) return false;
      if (search) {
        const q = search.toLowerCase();
        return r.businessName.toLowerCase().includes(q)
          || r.industry.toLowerCase().includes(q)
          || r.location.toLowerCase().includes(q)
          || r.contactName.toLowerCase().includes(q)
          || r.contactEmail.toLowerCase().includes(q);
      }
      return true;
    });
    if (sort === 'relevance') list = [...list].sort((a, b) => b.relevanceScore - a.relevanceScore);
    return list;
  }, [results, search, filters, sort]);

  const allSelected = filtered.length > 0 && filtered.every(r => selected.has(r.id));

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(filtered.map(r => r.id)));
  };

  const handleToggleSave = (id: string) => {
    setResults(prev => prev.map(r => r.id === id ? { ...r, savedForLater: !r.savedForLater } : r));
  };

  const handleAddToLeads = (id: string) => {
    setResults(prev => prev.map(r => r.id === id ? { ...r, addedToLeads: true } : r));
  };

  const activeFilterCount = [
    filters.industry !== 'all', filters.companySize !== 'all',
    filters.relevance !== 'all', filters.confidence !== 'all',
  ].filter(Boolean).length;

  return (
    <Box sx={{
      flex: 1, overflowY: 'auto',
      px: { xs: 2, sm: 3 }, py: { xs: 2, sm: 2.5 },
      '&::-webkit-scrollbar': { width: 4 },
      '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
    }}>
      <Box sx={{ maxWidth: 1300, mx: 'auto', display: 'flex', flexDirection: 'column', gap: 2.5, pb: 4 }}>

        {/* ── Header ── */}
        <Box sx={{
          display: 'flex', alignItems: { xs: 'flex-start', sm: 'center' },
          justifyContent: 'space-between', flexWrap: 'wrap', gap: 1.5,
          animation: 'fadeDown 0.3s ease-out',
          '@keyframes fadeDown': { from: { opacity: 0, transform: 'translateY(-8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        }}>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.3 }}>
              <Typography sx={{ fontSize: { xs: '1.25rem', sm: '1.45rem' }, fontWeight: 800, letterSpacing: '-0.025em', color: 'text.primary', lineHeight: 1.2 }}>
                Research
              </Typography>
              <Box sx={{
                px: 0.75, py: 0.25, borderRadius: '6px',
                background: isDark ? 'rgba(129,140,248,0.15)' : alpha(theme.palette.primary.main, 0.08),
                border: `1px solid ${isDark ? 'rgba(129,140,248,0.25)' : alpha(theme.palette.primary.main, 0.2)}`,
                display: 'flex', alignItems: 'center', gap: 0.4,
              }}>
                <AutoAwesomeRoundedIcon sx={{ fontSize: 10, color: isDark ? '#818cf8' : theme.palette.primary.main }} />
                <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: isDark ? '#818cf8' : theme.palette.primary.main }}>
                  AI-Powered
                </Typography>
              </Box>
            </Box>
            <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
              AI-powered business discovery engine
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Button
              startIcon={<CampaignRoundedIcon sx={{ fontSize: '15px !important' }} />}
              disabled={selected.size === 0}
              sx={{
                fontWeight: 700, fontSize: '0.75rem', px: 1.75, py: 0.8, borderRadius: '10px',
                textTransform: 'none', flexShrink: 0,
                border: `1px solid ${isDark ? 'rgba(255,255,255,0.12)' : theme.palette.divider}`,
                color: selected.size > 0 ? 'text.primary' : 'text.disabled',
                background: 'transparent',
                '&:hover': { background: isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.04) },
                '&.Mui-disabled': { opacity: 0.4 },
              }}
            >
              Add to Campaign {selected.size > 0 && `(${selected.size})`}
            </Button>
            <Button
              startIcon={<AddRoundedIcon sx={{ fontSize: '16px !important' }} />}
              sx={{
                background: grad, color: '#fff', fontWeight: 700,
                fontSize: '0.78rem', px: 2, py: 0.85, borderRadius: '10px',
                textTransform: 'none', flexShrink: 0,
                boxShadow: isDark ? '0 4px 20px rgba(129,140,248,0.3)' : '0 4px 20px rgba(67,56,202,0.25)',
                transition: 'all 0.2s ease',
                '&:hover': { opacity: 0.88, transform: 'translateY(-1px)' },
                '&:active': { transform: 'scale(0.98)' },
              }}
            >
              Start New Research
            </Button>
          </Box>
        </Box>

        {/* ── Summary stats ── */}
        <SummaryStats results={RESEARCH_RESULTS} isDark={isDark} theme={theme} />

        {/* ── Search + controls ── */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, flexWrap: 'wrap' }}>
          {/* Search */}
          <Box sx={{
            display: 'flex', alignItems: 'center', gap: 1,
            px: 1.25, py: 0.75, borderRadius: '10px',
            flex: { xs: '1 1 100%', sm: '1 1 280px' }, maxWidth: 360,
            background: isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04),
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider}`,
          }}>
            <SearchRoundedIcon sx={{ fontSize: 15, color: 'text.disabled', flexShrink: 0 }} />
            <InputBase
              placeholder="Search businesses, industries, locations..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              sx={{
                fontSize: '0.78rem', color: 'text.primary', flex: 1,
                '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 },
              }}
            />
            {search && (
              <IconButton size="small" onClick={() => setSearch('')} sx={{ p: 0.25, color: 'text.disabled' }}>
                <CloseRoundedIcon sx={{ fontSize: 13 }} />
              </IconButton>
            )}
          </Box>

          {/* Sort */}
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            {([
              { id: 'relevance', label: 'Most Relevant' },
              { id: 'recent',    label: 'Recently Added' },
            ] as const).map((s) => (
              <Box key={s.id} component="button" onClick={() => setSort(s.id)} sx={{
                px: 1.1, py: 0.45, borderRadius: '8px', border: 'none', cursor: 'pointer',
                fontSize: '0.7rem', fontWeight: sort === s.id ? 700 : 500,
                background: sort === s.id
                  ? isDark ? 'rgba(129,140,248,0.2)' : alpha(theme.palette.primary.main, 0.1)
                  : 'transparent',
                color: sort === s.id
                  ? isDark ? '#818cf8' : theme.palette.primary.main
                  : theme.palette.text.secondary,
                transition: 'all 0.15s ease',
                '&:hover': { background: isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.05) },
              }}>
                {s.label}
              </Box>
            ))}
          </Box>

          {/* Filter toggle */}
          <Box component="button" onClick={() => setShowFilters(v => !v)} sx={{
            display: 'flex', alignItems: 'center', gap: 0.6,
            px: 1.1, py: 0.5, borderRadius: '8px', border: 'none', cursor: 'pointer',
            fontSize: '0.7rem', fontWeight: 600,
            background: showFilters || activeFilterCount > 0
              ? isDark ? 'rgba(129,140,248,0.2)' : alpha(theme.palette.primary.main, 0.1)
              : isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04),
            color: showFilters || activeFilterCount > 0
              ? isDark ? '#818cf8' : theme.palette.primary.main
              : theme.palette.text.secondary,
            border: `1px solid ${showFilters || activeFilterCount > 0 ? (isDark ? 'rgba(129,140,248,0.3)' : alpha(theme.palette.primary.main, 0.25)) : (isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider)}`,
            transition: 'all 0.15s ease',
          }}>
            <FilterListRoundedIcon sx={{ fontSize: 14 }} />
            Filters
            {activeFilterCount > 0 && (
              <Box sx={{
                minWidth: 16, height: 16, borderRadius: '8px', px: 0.4,
                background: isDark ? '#818cf8' : theme.palette.primary.main,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Typography sx={{ fontSize: '0.52rem', fontWeight: 800, color: '#fff', lineHeight: 1 }}>
                  {activeFilterCount}
                </Typography>
              </Box>
            )}
          </Box>

          {/* View toggle */}
          <Box sx={{ display: 'flex', gap: 0.25, ml: 'auto' }}>
            {([
              { id: 'grid', Icon: GridViewRoundedIcon },
              { id: 'list', Icon: TableRowsRoundedIcon },
            ] as const).map(({ id, Icon }) => (
              <IconButton key={id} size="small" onClick={() => setViewMode(id)} sx={{
                width: 32, height: 32, borderRadius: '8px',
                color: viewMode === id ? (isDark ? '#818cf8' : theme.palette.primary.main) : 'text.secondary',
                background: viewMode === id
                  ? isDark ? 'rgba(129,140,248,0.15)' : alpha(theme.palette.primary.main, 0.08)
                  : 'transparent',
                border: `1px solid ${viewMode === id ? (isDark ? 'rgba(129,140,248,0.3)' : alpha(theme.palette.primary.main, 0.2)) : (isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider)}`,
              }}>
                <Icon sx={{ fontSize: 15 }} />
              </IconButton>
            ))}
          </Box>
        </Box>

        {/* ── Filter panel ── */}
        {showFilters && (
          <FilterPanel
            filters={filters}
            onChange={setFilters}
            isDark={isDark}
            theme={theme}
            onClose={() => setShowFilters(false)}
          />
        )}

        {/* ── Bulk action bar ── */}
        {selected.size > 0 && (
          <Box sx={{
            display: 'flex', alignItems: 'center', gap: 1.5,
            px: 2, py: 1.1, borderRadius: '12px',
            background: isDark ? 'rgba(129,140,248,0.1)' : alpha(theme.palette.primary.main, 0.06),
            border: `1px solid ${isDark ? 'rgba(129,140,248,0.25)' : alpha(theme.palette.primary.main, 0.2)}`,
            animation: 'slideIn 0.2s ease-out',
            '@keyframes slideIn': { from: { opacity: 0, transform: 'translateY(-4px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
          }}>
            <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: isDark ? '#818cf8' : theme.palette.primary.main }}>
              {selected.size} selected
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.75, ml: 'auto' }}>
              {[
                { label: 'Add to Leads', icon: PersonAddRoundedIcon, color: '#34d399' },
                { label: 'Add to Campaign', icon: CampaignRoundedIcon, color: isDark ? '#818cf8' : theme.palette.primary.main },
              ].map(({ label, icon: Icon, color }) => (
                <Box key={label} component="button" sx={{
                  display: 'flex', alignItems: 'center', gap: 0.5,
                  px: 1.25, py: 0.5, borderRadius: '8px', border: 'none', cursor: 'pointer',
                  fontSize: '0.7rem', fontWeight: 700, color,
                  background: alpha(color as string, isDark ? 0.12 : 0.08),
                  border: `1px solid ${alpha(color as string, 0.25)}`,
                  transition: 'all 0.15s ease',
                  '&:hover': { background: alpha(color as string, isDark ? 0.18 : 0.12) },
                }}>
                  <Icon sx={{ fontSize: 13 }} />
                  {label}
                </Box>
              ))}
              <Box component="button" onClick={() => setSelected(new Set())} sx={{
                px: 1, py: 0.5, borderRadius: '8px', border: 'none', cursor: 'pointer',
                fontSize: '0.7rem', fontWeight: 600, color: 'text.secondary',
                background: 'transparent',
                '&:hover': { background: isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.05) },
              }}>
                Clear
              </Box>
            </Box>
          </Box>
        )}

        {/* ── Results ── */}
        {filtered.length === 0 ? (
          <EmptyState isDark={isDark} grad={grad} onStart={() => { setSearch(''); setFilters({ industry: 'all', companySize: 'all', relevance: 'all', confidence: 'all' }); }} />
        ) : viewMode === 'grid' ? (
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', xl: 'repeat(3, 1fr)' }, gap: 2 }}>
            {filtered.map((r, i) => (
              <ResultCard
                key={r.id} result={r} isDark={isDark} theme={theme} index={i}
                selected={selected.has(r.id)} onSelect={toggleSelect}
                onToggleSave={handleToggleSave} onAddToLeads={handleAddToLeads}
              />
            ))}
          </Box>
        ) : (
          /* List view */
          <Box sx={{
            borderRadius: '14px', overflow: 'hidden',
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
            background: isDark ? 'rgba(255,255,255,0.02)' : theme.palette.background.paper,
          }}>
            {/* Table header */}
            <Box sx={{
              display: 'grid',
              gridTemplateColumns: '32px 1fr 160px 120px 80px 100px',
              alignItems: 'center', gap: 1.5,
              px: 1.75, py: 1,
              borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
              background: isDark ? 'rgba(255,255,255,0.03)' : alpha(theme.palette.text.primary, 0.02),
            }}>
              <Checkbox size="small" checked={allSelected} onChange={toggleAll} sx={{
                p: 0, color: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(15,23,42,0.2)',
                '&.Mui-checked': { color: isDark ? '#818cf8' : theme.palette.primary.main },
              }} />
              {['Business', 'Location', 'Confidence', 'Score', 'Actions'].map((h) => (
                <Typography key={h} sx={{ fontSize: '0.62rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                  {h}
                </Typography>
              ))}
            </Box>
            {filtered.map((r, i) => (
              <ResultRow
                key={r.id} result={r} isDark={isDark} theme={theme} index={i}
                selected={selected.has(r.id)} onSelect={toggleSelect}
                onToggleSave={handleToggleSave} onAddToLeads={handleAddToLeads}
              />
            ))}
          </Box>
        )}

        {/* ── Results count footer ── */}
        {filtered.length > 0 && (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', pt: 0.5 }}>
            <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>
              Showing {filtered.length} of {RESEARCH_RESULTS.length} results
              {activeFilterCount > 0 && ' · Filters active'}
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}
