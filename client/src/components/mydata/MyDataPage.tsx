'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import {
  Box, Typography, useTheme, alpha, InputBase,
  IconButton, Tooltip, Button, Modal, type Theme,
} from '@mui/material';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import StorageRoundedIcon from '@mui/icons-material/StorageRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import SyncRoundedIcon from '@mui/icons-material/SyncRounded';
import PauseCircleRoundedIcon from '@mui/icons-material/PauseCircleRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import EditRoundedIcon from '@mui/icons-material/EditRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import LinkRoundedIcon from '@mui/icons-material/LinkRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import UploadFileRoundedIcon from '@mui/icons-material/UploadFileRounded';
import TableChartRoundedIcon from '@mui/icons-material/TableChartRounded';
import ApiRoundedIcon from '@mui/icons-material/ApiRounded';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded';
import PaymentsRoundedIcon from '@mui/icons-material/PaymentsRounded';
import LocalOfferRoundedIcon from '@mui/icons-material/LocalOfferRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import EventRoundedIcon from '@mui/icons-material/EventRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import BusinessRoundedIcon from '@mui/icons-material/BusinessRounded';
import TuneRoundedIcon from '@mui/icons-material/TuneRounded';
import SpeedRoundedIcon from '@mui/icons-material/SpeedRounded';
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded';
import { lightGradients, darkGradients } from '@/theme/palette';
import {
  DATA_SOURCES, DATA_ENTRIES, CATEGORY_CONFIG, SOURCE_TYPE_CONFIG,
  SOURCE_STATUS_CONFIG, QUALITY_CONFIG, AI_RELEVANCE_CONFIG,
  getQualityLevel, DataEntry, DataCategory, DataSource,
} from './myDataData';

// ── Category icon map ─────────────────────────────────────────────────────────
const CATEGORY_ICONS: Record<DataCategory, React.ElementType> = {
  products:       InventoryRoundedIcon,
  pricing:        PaymentsRoundedIcon,
  offers:         LocalOfferRoundedIcon,
  business_hours: ScheduleRoundedIcon,
  meetings:       EventRoundedIcon,
  contacts:       PeopleRoundedIcon,
  company_info:   BusinessRoundedIcon,
  custom:         TuneRoundedIcon,
};

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

// ── Source status pill ────────────────────────────────────────────────────────
function SourcePill({ status }: { status: DataSource['status'] }) {
  const cfg = SOURCE_STATUS_CONFIG[status];
  const Icon = status === 'connected' ? CheckCircleRoundedIcon
    : status === 'syncing' ? SyncRoundedIcon
    : PauseCircleRoundedIcon;
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.4,
      px: 0.65, py: 0.15, borderRadius: '5px',
      background: cfg.bg, border: `1px solid ${alpha(cfg.color, 0.3)}`,
    }}>
      <Icon sx={{
        fontSize: 8, color: cfg.color,
        animation: status === 'syncing' ? 'spin 1.5s linear infinite' : 'none',
        '@keyframes spin': { from: { transform: 'rotate(0deg)' }, to: { transform: 'rotate(360deg)' } },
      }} />
      <Typography sx={{ fontSize: '0.52rem', fontWeight: 700, color: cfg.color, letterSpacing: '0.04em' }}>
        {cfg.label}
      </Typography>
    </Box>
  );
}

// ── AI relevance dot ──────────────────────────────────────────────────────────
function RelevanceDot({ level }: { level: keyof typeof AI_RELEVANCE_CONFIG }) {
  const cfg = AI_RELEVANCE_CONFIG[level];
  return (
    <Tooltip title={cfg.label} placement="top">
      <Box sx={{
        width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
        background: cfg.dot,
        boxShadow: level === 'critical' ? `0 0 5px ${cfg.dot}` : 'none',
      }} />
    </Tooltip>
  );
}

// ── Quality strip ─────────────────────────────────────────────────────────────
function QualityStrip({ score, isDark }: { score: number; isDark: boolean }) {
  const level = getQualityLevel(score);
  const color = QUALITY_CONFIG[level].color;
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
      <Box sx={{
        width: 56, height: 3, borderRadius: 2,
        background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)',
        overflow: 'hidden',
      }}>
        <Box sx={{
          height: '100%', borderRadius: 2, width: `${score}%`,
          background: color, transition: 'width 0.9s ease',
        }} />
      </Box>
      <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color, minWidth: 22 }}>{score}%</Typography>
    </Box>
  );
}

// ── Left nav panel ────────────────────────────────────────────────────────────
function LeftNav({
  entries, activeCategory, onSelect, isDark, theme, search, onSearch,
}: {
  entries: DataEntry[]; activeCategory: DataCategory | 'all' | 'sources';
  onSelect: (c: DataCategory | 'all' | 'sources') => void;
  isDark: boolean; theme: Theme; search: string; onSearch: (v: string) => void;
}) {
  const categories = Object.keys(CATEGORY_CONFIG) as DataCategory[];
  const countByCategory = useMemo(() => {
    const map: Record<string, number> = {};
    entries.forEach(e => { map[e.category] = (map[e.category] || 0) + 1; });
    return map;
  }, [entries]);

  const totalEntries = entries.length;
  const totalSources = DATA_SOURCES.length;

  return (
    <Box sx={{
      width: { xs: '100%', md: 220 },
      flexShrink: 0,
      borderRight: { md: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}` },
      display: 'flex', flexDirection: 'column',
      background: isDark ? 'rgba(255,255,255,0.015)' : alpha(theme.palette.text.primary, 0.01),
    }}>
      {/* Search */}
      <Box sx={{ px: 1.5, pt: 1.5, pb: 1 }}>
        <Box sx={{
          display: 'flex', alignItems: 'center', gap: 0.75,
          px: 1, py: 0.6, borderRadius: '8px',
          background: isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04),
          border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider}`,
        }}>
          <SearchRoundedIcon sx={{ fontSize: 13, color: 'text.disabled', flexShrink: 0 }} />
          <InputBase
            placeholder="Search data..."
            value={search}
            onChange={e => onSearch(e.target.value)}
            sx={{ fontSize: '0.72rem', color: 'text.primary', flex: 1, '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 } }}
          />
          {search && (
            <IconButton size="small" onClick={() => onSearch('')} sx={{ p: 0.15, color: 'text.disabled' }}>
              <CloseRoundedIcon sx={{ fontSize: 11 }} />
            </IconButton>
          )}
        </Box>
      </Box>

      {/* Nav items */}
      <Box sx={{ flex: 1, overflowY: 'auto', px: 1, pb: 2,
        '&::-webkit-scrollbar': { width: 3 },
        '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.15), borderRadius: 2 },
      }}>
        {/* All entries */}
        <NavItem
          label="All Data" count={totalEntries} active={activeCategory === 'all'}
          onClick={() => onSelect('all')} color="#818cf8" isDark={isDark} theme={theme}
          icon={<StorageRoundedIcon sx={{ fontSize: 13 }} />}
        />
        {/* Sources */}
        <NavItem
          label="Data Sources" count={totalSources} active={activeCategory === 'sources'}
          onClick={() => onSelect('sources')} color="#22d3ee" isDark={isDark} theme={theme}
          icon={<LinkRoundedIcon sx={{ fontSize: 13 }} />}
        />

        {/* Divider */}
        <Box sx={{ mx: 0.5, my: 1, height: '1px', background: isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider }} />

        {/* Category label */}
        <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.1em', px: 0.75, mb: 0.5 }}>
          Categories
        </Typography>

        {categories.map(cat => {
          const cfg = CATEGORY_CONFIG[cat];
          const Icon = CATEGORY_ICONS[cat];
          const count = countByCategory[cat] || 0;
          if (count === 0) return null;
          return (
            <NavItem
              key={cat} label={cfg.label} count={count}
              active={activeCategory === cat}
              onClick={() => onSelect(cat)}
              color={cfg.color} isDark={isDark} theme={theme}
              icon={<Icon sx={{ fontSize: 13 }} />}
            />
          );
        })}
      </Box>

      {/* Bottom: AI health */}
      <Box sx={{
        mx: 1.5, mb: 1.5, p: 1.25, borderRadius: '10px',
        background: isDark ? 'rgba(192,132,252,0.07)' : alpha('#c084fc', 0.05),
        border: `1px solid ${alpha('#c084fc', isDark ? 0.18 : 0.15)}`,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.75 }}>
          <AutoAwesomeRoundedIcon sx={{ fontSize: 11, color: '#c084fc' }} />
          <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: '#c084fc' }}>AI Health</Typography>
        </Box>
        {[
          { label: 'Data completeness', value: 87, color: '#34d399' },
          { label: 'AI-ready entries',  value: 91, color: '#818cf8' },
        ].map(({ label, value, color }) => (
          <Box key={label} sx={{ mb: 0.6 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.3 }}>
              <Typography sx={{ fontSize: '0.58rem', color: 'text.disabled' }}>{label}</Typography>
              <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color }}>{value}%</Typography>
            </Box>
            <Box sx={{ height: 3, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)', overflow: 'hidden' }}>
              <Box sx={{ height: '100%', borderRadius: 2, width: `${value}%`, background: color, transition: 'width 1s ease' }} />
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

function NavItem({ label, count, active, onClick, color, isDark, theme, icon }: {
  label: string; count: number; active: boolean; onClick: () => void;
  color: string; isDark: boolean; theme: Theme; icon: React.ReactNode;
}) {
  return (
    <Box component="button" onClick={onClick} sx={{
      width: '100%', display: 'flex', alignItems: 'center', gap: 0.75,
      px: 0.75, py: 0.65, borderRadius: '8px', border: 'none', cursor: 'pointer',
      textAlign: 'left', mb: 0.25,
      background: active
        ? isDark ? alpha(color, 0.14) : alpha(color, 0.09)
        : 'transparent',
      color: active ? color : theme.palette.text.secondary,
      transition: 'all 0.15s ease',
      '&:hover': {
        background: active
          ? isDark ? alpha(color, 0.18) : alpha(color, 0.12)
          : isDark ? 'rgba(255,255,255,0.04)' : alpha(theme.palette.text.primary, 0.03),
        color: active ? color : theme.palette.text.primary,
      },
    }}>
      <Box sx={{ color: 'inherit', display: 'flex', alignItems: 'center', flexShrink: 0 }}>{icon}</Box>
      <Typography sx={{ fontSize: '0.75rem', fontWeight: active ? 700 : 500, color: 'inherit', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {label}
      </Typography>
      {count > 0 && (
        <Box sx={{
          minWidth: 18, height: 16, px: 0.5, borderRadius: '5px',
          background: active ? alpha(color, isDark ? 0.25 : 0.15) : isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.06),
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: active ? color : 'text.disabled', lineHeight: 1 }}>{count}</Typography>
        </Box>
      )}
    </Box>
  );
}

// ── Entry detail panel ────────────────────────────────────────────────────────
function EntryPanel({ entry, isDark, theme, onClose }: {
  entry: DataEntry; isDark: boolean; theme: Theme; onClose: () => void;
}) {
  const catCfg = CATEGORY_CONFIG[entry.category];
  const level = getQualityLevel(entry.qualityScore);
  const qualCfg = QUALITY_CONFIG[level];

  return (
    <Box sx={{
      position: 'fixed', inset: 0, zIndex: 1300,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)',
      p: 2,
    }} onClick={onClose}>
      <Box sx={{
        width: '100%', maxWidth: 560, maxHeight: '85vh',
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
          background: isDark ? alpha(entry.accentColor, 0.05) : alpha(entry.accentColor, 0.03),
        }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0 }}>
              <Box sx={{
                width: 36, height: 36, borderRadius: '10px', flexShrink: 0,
                background: alpha(entry.accentColor, isDark ? 0.2 : 0.12),
                border: `1.5px solid ${alpha(entry.accentColor, 0.3)}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {(() => { const Icon = CATEGORY_ICONS[entry.category]; return <Icon sx={{ fontSize: 17, color: entry.accentColor }} />; })()}
              </Box>
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: '1rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
                  {entry.title}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.4, flexWrap: 'wrap' }}>
                  <Box sx={{ px: 0.65, py: 0.15, borderRadius: '5px', background: alpha(catCfg.color, isDark ? 0.15 : 0.1), border: `1px solid ${alpha(catCfg.color, 0.25)}` }}>
                    <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: catCfg.color }}>{catCfg.label}</Typography>
                  </Box>
                  <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>via {entry.sourceName}</Typography>
                  <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>· {entry.updatedAt}</Typography>
                </Box>
              </Box>
            </Box>
            <IconButton size="small" onClick={onClose} sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary', flexShrink: 0, '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) } }}>
              <CloseRoundedIcon sx={{ fontSize: 15 }} />
            </IconButton>
          </Box>
          {/* Quality + used in */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <SpeedRoundedIcon sx={{ fontSize: 11, color: 'text.disabled' }} />
              <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>Quality</Typography>
              <QualityStrip score={entry.qualityScore} isDark={isDark} />
              <Box sx={{ px: 0.55, py: 0.1, borderRadius: '5px', background: isDark ? qualCfg.darkBg : qualCfg.bg, border: `1px solid ${alpha(qualCfg.color, 0.3)}` }}>
                <Typography sx={{ fontSize: '0.52rem', fontWeight: 700, color: qualCfg.color }}>{qualCfg.label}</Typography>
              </Box>
            </Box>
            {entry.usedIn.length > 0 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                <LinkRoundedIcon sx={{ fontSize: 11, color: isDark ? '#818cf8' : theme.palette.primary.main }} />
                <Typography sx={{ fontSize: '0.62rem', fontWeight: 600, color: isDark ? '#818cf8' : theme.palette.primary.main }}>
                  {entry.usedIn.length} campaign{entry.usedIn.length > 1 ? 's' : ''}
                </Typography>
              </Box>
            )}
          </Box>
        </Box>

        {/* Fields */}
        <Box sx={{ flex: 1, overflowY: 'auto', p: 2,
          '&::-webkit-scrollbar': { width: 4 },
          '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
        }}>
          {entry.missingFields.length > 0 && (
            <Box sx={{
              display: 'flex', alignItems: 'flex-start', gap: 0.75, mb: 1.75,
              px: 1.25, py: 0.9, borderRadius: '10px',
              background: isDark ? 'rgba(251,191,36,0.07)' : 'rgba(251,191,36,0.05)',
              border: `1px solid ${isDark ? 'rgba(251,191,36,0.2)' : 'rgba(251,191,36,0.18)'}`,
            }}>
              <WarningAmberRoundedIcon sx={{ fontSize: 13, color: '#fbbf24', mt: 0.1, flexShrink: 0 }} />
              <Typography sx={{ fontSize: '0.7rem', color: isDark ? alpha('#fbbf24', 0.9) : '#b45309', lineHeight: 1.5 }}>
                Missing fields: {entry.missingFields.join(', ')} — adding these will improve AI accuracy.
              </Typography>
            </Box>
          )}

          {/* Field rows */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {entry.fields.map((field, i) => (
              <Box key={field.key} sx={{
                display: 'grid', gridTemplateColumns: '28px 140px 1fr',
                alignItems: 'flex-start', gap: 1,
                py: 0.9, px: 0.5,
                borderBottom: i < entry.fields.length - 1
                  ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : theme.palette.divider}`
                  : 'none',
                '&:hover': { background: isDark ? 'rgba(255,255,255,0.02)' : alpha(theme.palette.text.primary, 0.015), borderRadius: '6px' },
                transition: 'background 0.12s ease',
              }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', pt: 0.2 }}>
                  <RelevanceDot level={field.aiRelevance} />
                </Box>
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: 'text.secondary', pt: 0.1 }}>
                  {field.label}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
                  {field.type === 'url' ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                      <Typography sx={{ fontSize: '0.75rem', color: isDark ? '#818cf8' : theme.palette.primary.main, fontWeight: 500, wordBreak: 'break-all' }}>
                        {field.value}
                      </Typography>
                      <OpenInNewRoundedIcon sx={{ fontSize: 11, color: isDark ? '#818cf8' : theme.palette.primary.main, flexShrink: 0 }} />
                    </Box>
                  ) : field.type === 'list' ? (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.4 }}>
                      {field.value.split(',').map(v => (
                        <Box key={v.trim()} sx={{
                          px: 0.65, py: 0.15, borderRadius: '5px',
                          background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05),
                          border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
                        }}>
                          <Typography sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>{v.trim()}</Typography>
                        </Box>
                      ))}
                    </Box>
                  ) : (
                    <Typography sx={{ fontSize: '0.75rem', color: 'text.primary', fontWeight: 500, lineHeight: 1.5 }}>
                      {field.value}
                    </Typography>
                  )}
                </Box>
              </Box>
            ))}
          </Box>
        </Box>

        {/* Footer actions */}
        <Box sx={{
          px: 2.5, py: 1.5,
          borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
          display: 'flex', gap: 0.75, justifyContent: 'flex-end',
        }}>
          <Button size="small" startIcon={<EditRoundedIcon sx={{ fontSize: '13px !important' }} />} sx={{
            fontSize: '0.72rem', fontWeight: 600, px: 1.5, py: 0.6, borderRadius: '8px', textTransform: 'none',
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.12)' : theme.palette.divider}`,
            color: 'text.primary', background: 'transparent',
            '&:hover': { background: isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.04) },
          }}>Edit</Button>
          <Button size="small" startIcon={<DeleteOutlineRoundedIcon sx={{ fontSize: '13px !important' }} />} sx={{
            fontSize: '0.72rem', fontWeight: 600, px: 1.5, py: 0.6, borderRadius: '8px', textTransform: 'none',
            border: `1px solid rgba(239,68,68,0.25)`, color: '#ef4444', background: 'transparent',
            '&:hover': { background: 'rgba(239,68,68,0.08)' },
          }}>Delete</Button>
        </Box>
      </Box>
    </Box>
  );
}

// ── Entry row (inline table row style) ───────────────────────────────────────
function EntryRow({ entry, isDark, theme, index, onClick }: {
  entry: DataEntry; isDark: boolean; theme: Theme; index: number; onClick: () => void;
}) {
  const catCfg = CATEGORY_CONFIG[entry.category];
  const level = getQualityLevel(entry.qualityScore);
  const qualColor = QUALITY_CONFIG[level].color;
  const Icon = CATEGORY_ICONS[entry.category];

  return (
    <Box component="button" onClick={onClick} sx={{
      width: '100%', display: 'grid',
      gridTemplateColumns: '28px 1fr 110px 80px 70px 80px',
      alignItems: 'center', gap: 1.5,
      px: 1.5, py: 1,
      border: 'none', cursor: 'pointer', textAlign: 'left',
      borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : theme.palette.divider}`,
      background: 'transparent',
      transition: 'background 0.12s ease',
      '&:hover': {
        background: isDark ? 'rgba(255,255,255,0.025)' : alpha(theme.palette.text.primary, 0.02),
      },
      animation: `rowIn 0.22s ease-out ${index * 0.04}s both`,
      '@keyframes rowIn': { from: { opacity: 0, transform: 'translateX(-4px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
    }}>
      {/* Category icon */}
      <Box sx={{
        width: 26, height: 26, borderRadius: '7px', flexShrink: 0,
        background: alpha(catCfg.color, isDark ? 0.15 : 0.1),
        border: `1px solid ${alpha(catCfg.color, 0.2)}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon sx={{ fontSize: 13, color: catCfg.color }} />
      </Box>

      {/* Title + preview */}
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontSize: '0.8rem', fontWeight: 700, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', lineHeight: 1.3 }}>
          {entry.title}
        </Typography>
        <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', mt: 0.15 }}>
          {entry.fields[0]?.value || '—'}
        </Typography>
      </Box>

      {/* Category */}
      <Box sx={{ px: 0.65, py: 0.2, borderRadius: '5px', background: alpha(catCfg.color, isDark ? 0.12 : 0.08), border: `1px solid ${alpha(catCfg.color, 0.2)}`, display: 'inline-flex', alignSelf: 'center' }}>
        <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: catCfg.color }}>{catCfg.label}</Typography>
      </Box>

      {/* Quality */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Box sx={{ width: 32, height: 3, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)', overflow: 'hidden' }}>
          <Box sx={{ height: '100%', borderRadius: 2, width: `${entry.qualityScore}%`, background: qualColor }} />
        </Box>
        <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: qualColor }}>{entry.qualityScore}%</Typography>
      </Box>

      {/* Used in */}
      <Box>
        {entry.usedIn.length > 0 ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.3 }}>
            <LinkRoundedIcon sx={{ fontSize: 10, color: isDark ? '#818cf8' : theme.palette.primary.main }} />
            <Typography sx={{ fontSize: '0.62rem', fontWeight: 600, color: isDark ? '#818cf8' : theme.palette.primary.main }}>{entry.usedIn.length}</Typography>
          </Box>
        ) : (
          <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>—</Typography>
        )}
      </Box>

      {/* Updated */}
      <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', textAlign: 'right' }}>{entry.updatedAt}</Typography>
    </Box>
  );
}

// ── Category section ──────────────────────────────────────────────────────────
function CategorySection({ category, entries, isDark, theme, onEntryClick }: {
  category: DataCategory; entries: DataEntry[]; isDark: boolean; theme: Theme;
  onEntryClick: (e: DataEntry) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const cfg = CATEGORY_CONFIG[category];
  const Icon = CATEGORY_ICONS[category];
  const avgQuality = Math.round(entries.reduce((s, e) => s + e.qualityScore, 0) / entries.length);
  const qualColor = avgQuality >= 75 ? '#34d399' : avgQuality >= 45 ? '#fbbf24' : '#f87171';

  return (
    <Box sx={{
      borderRadius: '14px', overflow: 'hidden',
      border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
      background: isDark ? 'rgba(255,255,255,0.02)' : theme.palette.background.paper,
      animation: 'sectionIn 0.3s ease-out both',
      '@keyframes sectionIn': { from: { opacity: 0, transform: 'translateY(6px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
    }}>
      {/* Section header — clickable to collapse */}
      <Box component="button" onClick={() => setCollapsed(v => !v)} sx={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 1.25,
        px: 1.75, py: 1.25, border: 'none', cursor: 'pointer', textAlign: 'left',
        background: isDark ? alpha(cfg.color, 0.05) : alpha(cfg.color, 0.03),
        borderBottom: collapsed ? 'none' : `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
        transition: 'background 0.15s ease',
        '&:hover': { background: isDark ? alpha(cfg.color, 0.08) : alpha(cfg.color, 0.05) },
      }}>
        {/* Left accent line */}
        <Box sx={{ width: 3, height: 28, borderRadius: 2, background: cfg.color, flexShrink: 0 }} />
        <Box sx={{
          width: 30, height: 30, borderRadius: '9px', flexShrink: 0,
          background: alpha(cfg.color, isDark ? 0.18 : 0.12),
          border: `1px solid ${alpha(cfg.color, 0.25)}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon sx={{ fontSize: 15, color: cfg.color }} />
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontSize: '0.88rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.01em', lineHeight: 1.2 }}>
            {cfg.label}
          </Typography>
          <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', mt: 0.1 }}>{cfg.description}</Typography>
        </Box>
        {/* Stats */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexShrink: 0 }}>
          <Box sx={{ textAlign: 'right' }}>
            <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>Avg quality</Typography>
            <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: qualColor }}>{avgQuality}%</Typography>
          </Box>
          <Box sx={{
            minWidth: 22, height: 20, px: 0.6, borderRadius: '6px',
            background: alpha(cfg.color, isDark ? 0.18 : 0.1),
            border: `1px solid ${alpha(cfg.color, 0.25)}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Typography sx={{ fontSize: '0.62rem', fontWeight: 800, color: cfg.color }}>{entries.length}</Typography>
          </Box>
          <ExpandMoreRoundedIcon sx={{
            fontSize: 16, color: 'text.disabled',
            transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease',
          }} />
        </Box>
      </Box>

      {/* Table header */}
      {!collapsed && (
        <>
          <Box sx={{
            display: 'grid', gridTemplateColumns: '28px 1fr 110px 80px 70px 80px',
            alignItems: 'center', gap: 1.5, px: 1.5, py: 0.65,
            background: isDark ? 'rgba(255,255,255,0.02)' : alpha(theme.palette.text.primary, 0.015),
            borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : theme.palette.divider}`,
          }}>
            <Box />
            {['Entry', 'Category', 'Quality', 'Used In', 'Updated'].map(h => (
              <Typography key={h} sx={{ fontSize: '0.58rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                {h}
              </Typography>
            ))}
          </Box>
          {entries.map((entry, i) => (
            <EntryRow key={entry.id} entry={entry} isDark={isDark} theme={theme} index={i} onClick={() => onEntryClick(entry)} />
          ))}
        </>
      )}
    </Box>
  );
}

// ── Sources view ──────────────────────────────────────────────────────────────
function SourcesView({ isDark, theme }: { isDark: boolean; theme: Theme }) {
  const totalRecords = DATA_SOURCES.reduce((s, src) => s + src.records, 0);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {/* Header strip */}
      <Box sx={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        px: 1.75, py: 1.25, borderRadius: '12px',
        background: isDark ? 'rgba(34,211,238,0.06)' : alpha('#22d3ee', 0.04),
        border: `1px solid ${alpha('#22d3ee', isDark ? 0.18 : 0.15)}`,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <LinkRoundedIcon sx={{ fontSize: 14, color: '#22d3ee' }} />
          <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary' }}>Data Sources</Typography>
          <Box sx={{ px: 0.65, py: 0.15, borderRadius: '5px', background: alpha('#22d3ee', 0.15), border: `1px solid ${alpha('#22d3ee', 0.25)}` }}>
            <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: '#22d3ee' }}>{DATA_SOURCES.length} connected</Typography>
          </Box>
        </Box>
        <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary' }}>{totalRecords.toLocaleString()} total records</Typography>
      </Box>

      {/* Source rows */}
      <Box sx={{
        borderRadius: '14px', overflow: 'hidden',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
        background: isDark ? 'rgba(255,255,255,0.02)' : theme.palette.background.paper,
      }}>
        {/* Table header */}
        <Box sx={{
          display: 'grid', gridTemplateColumns: '1fr 100px 80px 90px 80px',
          alignItems: 'center', gap: 1.5, px: 1.75, py: 0.75,
          background: isDark ? 'rgba(255,255,255,0.03)' : alpha(theme.palette.text.primary, 0.02),
          borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
        }}>
          {['Source', 'Type', 'Records', 'AI-Ready', 'Status'].map(h => (
            <Typography key={h} sx={{ fontSize: '0.58rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
              {h}
            </Typography>
          ))}
        </Box>

        {DATA_SOURCES.map((src, i) => {
          const typeCfg = SOURCE_TYPE_CONFIG[src.type];
          const aiColor = src.aiReadyPct >= 75 ? '#34d399' : src.aiReadyPct >= 50 ? '#fbbf24' : '#f87171';
          return (
            <Box key={src.id} sx={{
              display: 'grid', gridTemplateColumns: '1fr 100px 80px 90px 80px',
              alignItems: 'center', gap: 1.5, px: 1.75, py: 1.1,
              borderBottom: i < DATA_SOURCES.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : theme.palette.divider}` : 'none',
              transition: 'background 0.12s ease',
              '&:hover': { background: isDark ? 'rgba(255,255,255,0.025)' : alpha(theme.palette.text.primary, 0.02) },
              animation: `rowIn 0.22s ease-out ${i * 0.05}s both`,
              '@keyframes rowIn': { from: { opacity: 0, transform: 'translateX(-4px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
            }}>
              <Box>
                <Typography sx={{ fontSize: '0.8rem', fontWeight: 700, color: 'text.primary' }}>{src.name}</Typography>
                <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', mt: 0.1 }}>Last sync: {src.lastSync}</Typography>
              </Box>
              <Box sx={{ px: 0.65, py: 0.2, borderRadius: '5px', background: alpha(typeCfg.color, isDark ? 0.12 : 0.08), border: `1px solid ${alpha(typeCfg.color, 0.2)}`, display: 'inline-flex', alignSelf: 'center' }}>
                <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: typeCfg.color }}>{typeCfg.label}</Typography>
              </Box>
              <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: 'text.primary' }}>{src.records.toLocaleString()}</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6 }}>
                <Box sx={{ flex: 1, height: 3, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)', overflow: 'hidden' }}>
                  <Box sx={{ height: '100%', borderRadius: 2, width: `${src.aiReadyPct}%`, background: aiColor, transition: 'width 0.9s ease' }} />
                </Box>
                <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: aiColor, minWidth: 26 }}>{src.aiReadyPct}%</Typography>
              </Box>
              <SourcePill status={src.status} />
            </Box>
          );
        })}
      </Box>

      {/* Used in breakdown */}
      <Box sx={{
        borderRadius: '14px', overflow: 'hidden',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
        background: isDark ? 'rgba(255,255,255,0.02)' : theme.palette.background.paper,
      }}>
        <Box sx={{ px: 1.75, py: 1.1, borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`, display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <AutoAwesomeRoundedIcon sx={{ fontSize: 13, color: '#c084fc' }} />
          <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: 'text.primary' }}>Campaign Usage</Typography>
        </Box>
        <Box sx={{ p: 1.75, display: 'flex', flexDirection: 'column', gap: 0.75 }}>
          {DATA_SOURCES.filter(s => s.usedIn.length > 0).map(src => (
            <Box key={src.id} sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
              <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: 'text.secondary', minWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {src.name}
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {src.usedIn.map(name => (
                  <Box key={name} sx={{
                    px: 0.65, py: 0.15, borderRadius: '5px',
                    background: isDark ? 'rgba(129,140,248,0.1)' : alpha(theme.palette.primary.main, 0.07),
                    border: `1px solid ${isDark ? 'rgba(129,140,248,0.2)' : alpha(theme.palette.primary.main, 0.15)}`,
                  }}>
                    <Typography sx={{ fontSize: '0.58rem', fontWeight: 600, color: isDark ? '#818cf8' : theme.palette.primary.main }}>{name}</Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          ))}
        </Box>
      </Box>
    </Box>
  );
}

// ── Add data modal ────────────────────────────────────────────────────────────
function AddDataModal({ open, onClose, isDark, theme }: {
  open: boolean; onClose: () => void; isDark: boolean; theme: Theme;
}) {
  const [step, setStep] = useState<'choose' | 'csv' | 'manual' | 'sheets' | 'api'>('choose');

  const options = [
    { id: 'csv' as const,    icon: UploadFileRoundedIcon,  label: 'Upload CSV',       desc: 'Import from a CSV file',              color: '#34d399' },
    { id: 'manual' as const, icon: EditRoundedIcon,        label: 'Manual Entry',     desc: 'Add data fields manually',            color: '#c084fc' },
    { id: 'sheets' as const, icon: TableChartRoundedIcon,  label: 'Google Sheets',    desc: 'Sync from a spreadsheet',             color: '#60a5fa' },
    { id: 'api' as const,    icon: ApiRoundedIcon,         label: 'API / Webhook',    desc: 'Connect via REST API',                color: '#22d3ee' },
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

  const categories = Object.keys(CATEGORY_CONFIG) as DataCategory[];

  return (
    <Modal open={open} onClose={() => { onClose(); setStep('choose'); }} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
      <Box sx={{
        width: '100%', maxWidth: 480,
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
            <Typography sx={{ fontSize: '1rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em' }}>
              {step === 'choose' ? 'Add Business Data' : step === 'csv' ? 'Upload CSV' : step === 'manual' ? 'Manual Entry' : step === 'sheets' ? 'Connect Google Sheets' : 'API / Webhook'}
            </Typography>
            <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', mt: 0.3 }}>
              {step === 'choose' ? 'Choose how to add data for your AI' : 'Fill in the details below'}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            {step !== 'choose' && (
              <IconButton size="small" onClick={() => setStep('choose')} sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary', '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) } }}>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 700 }}>←</Typography>
              </IconButton>
            )}
            <IconButton size="small" onClick={() => { onClose(); setStep('choose'); }} sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary', '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) } }}>
              <CloseRoundedIcon sx={{ fontSize: 15 }} />
            </IconButton>
          </Box>
        </Box>

        {/* Choose step */}
        {step === 'choose' && (
          <Box sx={{ p: 2, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.25 }}>
            {options.map(opt => (
              <Box key={opt.id} component="button" onClick={() => setStep(opt.id)} sx={{
                display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 0.75,
                p: 1.5, borderRadius: '12px', cursor: 'pointer', textAlign: 'left',
                background: isDark ? alpha(opt.color, 0.07) : alpha(opt.color, 0.05),
                border: `1.5px solid ${alpha(opt.color, isDark ? 0.2 : 0.15)}`,
                transition: 'all 0.18s ease',
                '&:hover': { transform: 'translateY(-2px)', boxShadow: isDark ? '0 8px 24px rgba(0,0,0,0.3)' : '0 8px 24px rgba(15,23,42,0.08)', borderColor: opt.color },
                '&:active': { transform: 'scale(0.99)' },
              }}>
                <Box sx={{ width: 34, height: 34, borderRadius: '9px', background: alpha(opt.color, 0.15), border: `1px solid ${alpha(opt.color, 0.25)}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <opt.icon sx={{ fontSize: 17, color: opt.color }} />
                </Box>
                <Box>
                  <Typography sx={{ fontSize: '0.8rem', fontWeight: 700, color: 'text.primary' }}>{opt.label}</Typography>
                  <Typography sx={{ fontSize: '0.63rem', color: 'text.secondary', mt: 0.15, lineHeight: 1.4 }}>{opt.desc}</Typography>
                </Box>
              </Box>
            ))}
          </Box>
        )}

        {/* CSV step */}
        {step === 'csv' && (
          <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <Box sx={{
              border: `2px dashed ${isDark ? 'rgba(52,211,153,0.3)' : 'rgba(52,211,153,0.4)'}`,
              borderRadius: '12px', p: 3, textAlign: 'center', cursor: 'pointer',
              background: isDark ? 'rgba(52,211,153,0.05)' : 'rgba(52,211,153,0.03)',
              '&:hover': { background: isDark ? 'rgba(52,211,153,0.09)' : 'rgba(52,211,153,0.06)', borderColor: '#34d399' },
              transition: 'all 0.18s ease',
            }}>
              <UploadFileRoundedIcon sx={{ fontSize: 30, color: '#34d399', mb: 0.75 }} />
              <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary', mb: 0.3 }}>Drop CSV file here</Typography>
              <Typography sx={{ fontSize: '0.67rem', color: 'text.secondary' }}>or click to browse · Max 10MB</Typography>
            </Box>
            <Box component="button" sx={{ width: '100%', border: 'none', cursor: 'pointer', py: 0.9, borderRadius: '10px', background: 'linear-gradient(135deg, #34d399, #22d3ee)', color: '#fff', fontSize: '0.78rem', fontWeight: 700, transition: 'opacity 0.15s ease', '&:hover': { opacity: 0.88 } }}>
              Upload & Import
            </Box>
          </Box>
        )}

        {/* Manual entry step */}
        {step === 'manual' && (
          <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.1 }}>
            <Box>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Data Category</Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 0.5 }}>
                {categories.slice(0, 8).map(cat => {
                  const cfg = CATEGORY_CONFIG[cat];
                  const Icon = CATEGORY_ICONS[cat];
                  return (
                    <Box key={cat} component="button" sx={{
                      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.4,
                      p: 0.75, borderRadius: '8px', cursor: 'pointer', border: 'none',
                      background: isDark ? alpha(cfg.color, 0.08) : alpha(cfg.color, 0.06),
                      border: `1px solid ${alpha(cfg.color, 0.2)}`,
                      transition: 'all 0.15s ease',
                      '&:hover': { background: isDark ? alpha(cfg.color, 0.15) : alpha(cfg.color, 0.1) },
                    }}>
                      <Icon sx={{ fontSize: 14, color: cfg.color }} />
                      <Typography sx={{ fontSize: '0.52rem', fontWeight: 600, color: cfg.color, textAlign: 'center', lineHeight: 1.2 }}>{cfg.label}</Typography>
                    </Box>
                  );
                })}
              </Box>
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Entry Title</Typography>
              <InputBase placeholder="e.g. Pro Plan Pricing, Business Hours..." sx={inputSx} fullWidth />
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Data Content</Typography>
              <InputBase
                placeholder="Describe the data in detail — the more complete, the better AI output..."
                multiline rows={3}
                sx={{ ...inputSx, alignItems: 'flex-start', '& textarea': { resize: 'none' } }}
                fullWidth
              />
            </Box>
            <Box component="button" sx={{ width: '100%', border: 'none', cursor: 'pointer', py: 0.9, borderRadius: '10px', background: 'linear-gradient(135deg, #c084fc, #818cf8)', color: '#fff', fontSize: '0.78rem', fontWeight: 700, mt: 0.25, transition: 'opacity 0.15s ease', '&:hover': { opacity: 0.88 } }}>
              Save Entry
            </Box>
          </Box>
        )}

        {/* Google Sheets step */}
        {step === 'sheets' && (
          <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
            <Box>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Google Sheets URL</Typography>
              <InputBase placeholder="https://docs.google.com/spreadsheets/d/..." sx={inputSx} fullWidth />
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Sheet Name (optional)</Typography>
              <InputBase placeholder="Sheet1" sx={inputSx} fullWidth />
            </Box>
            <Box sx={{ px: 1.25, py: 1, borderRadius: '9px', background: isDark ? 'rgba(96,165,250,0.07)' : 'rgba(96,165,250,0.05)', border: `1px solid ${alpha('#60a5fa', 0.2)}` }}>
              <Typography sx={{ fontSize: '0.65rem', color: isDark ? '#60a5fa' : '#0891b2', fontWeight: 500, lineHeight: 1.5 }}>
                Share the sheet with "Anyone with the link" before connecting.
              </Typography>
            </Box>
            <Box component="button" sx={{ width: '100%', border: 'none', cursor: 'pointer', py: 0.9, borderRadius: '10px', background: 'linear-gradient(135deg, #60a5fa, #22d3ee)', color: '#fff', fontSize: '0.78rem', fontWeight: 700, transition: 'opacity 0.15s ease', '&:hover': { opacity: 0.88 } }}>
              Connect Sheet
            </Box>
          </Box>
        )}

        {/* API step */}
        {step === 'api' && (
          <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
            <Box>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Source Name</Typography>
              <InputBase placeholder="e.g. Pricing API" sx={inputSx} fullWidth />
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', mb: 0.5 }}>Endpoint URL</Typography>
              <InputBase placeholder="https://api.yoursource.com/data" sx={inputSx} fullWidth />
            </Box>
            <Box sx={{ px: 1.25, py: 1, borderRadius: '9px', background: isDark ? 'rgba(34,211,238,0.07)' : 'rgba(34,211,238,0.05)', border: `1px solid ${alpha('#22d3ee', 0.2)}` }}>
              <Typography sx={{ fontSize: '0.65rem', color: isDark ? '#22d3ee' : '#0891b2', fontWeight: 500, lineHeight: 1.5 }}>
                We'll poll this endpoint every 15 minutes. Expected: JSON object or array.
              </Typography>
            </Box>
            <Box component="button" sx={{ width: '100%', border: 'none', cursor: 'pointer', py: 0.9, borderRadius: '10px', background: 'linear-gradient(135deg, #22d3ee, #818cf8)', color: '#fff', fontSize: '0.78rem', fontWeight: 700, transition: 'opacity 0.15s ease', '&:hover': { opacity: 0.88 } }}>
              Connect API
            </Box>
          </Box>
        )}
      </Box>
    </Modal>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function MyDataPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients.primary : lightGradients.primary;

  const [activeCategory, setActiveCategory] = useState<DataCategory | 'all' | 'sources'>('all');
  const [search, setSearch] = useState('');
  const [selectedEntry, setSelectedEntry] = useState<DataEntry | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const filteredEntries = useMemo(() => {
    return DATA_ENTRIES.filter(e => {
      if (activeCategory !== 'all' && activeCategory !== 'sources' && e.category !== activeCategory) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          e.title.toLowerCase().includes(q) ||
          e.fields.some(f => f.value.toLowerCase().includes(q) || f.label.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [activeCategory, search]);

  // Group by category for "all" view
  const groupedEntries = useMemo(() => {
    const map = new Map<DataCategory, DataEntry[]>();
    filteredEntries.forEach(e => {
      if (!map.has(e.category)) map.set(e.category, []);
      map.get(e.category)!.push(e);
    });
    return map;
  }, [filteredEntries]);

  const totalEntries = DATA_ENTRIES.length;
  const totalSources = DATA_SOURCES.length;
  const avgQuality = Math.round(DATA_ENTRIES.reduce((s, e) => s + e.qualityScore, 0) / DATA_ENTRIES.length);
  const aiReady = DATA_ENTRIES.filter(e => e.qualityScore >= 75).length;

  return (
    <Box sx={{
      flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0,
    }}>
      {/* ── Top header bar ── */}
      <Box sx={{
        px: { xs: 2, sm: 3 }, py: 1.5, flexShrink: 0,
        borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
        background: isDark ? 'rgba(8,13,24,0.8)' : theme.palette.background.paper,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap',
        animation: 'fadeDown 0.3s ease-out',
        '@keyframes fadeDown': { from: { opacity: 0, transform: 'translateY(-6px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
      }}>
        {/* Left: title + stats inline */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Typography sx={{ fontSize: { xs: '1.1rem', sm: '1.25rem' }, fontWeight: 800, letterSpacing: '-0.025em', color: 'text.primary', lineHeight: 1 }}>
                My Data
              </Typography>
              <Box sx={{
                px: 0.65, py: 0.2, borderRadius: '6px',
                background: isDark ? 'rgba(192,132,252,0.15)' : alpha('#c084fc', 0.08),
                border: `1px solid ${alpha('#c084fc', 0.25)}`,
                display: 'flex', alignItems: 'center', gap: 0.35,
              }}>
                <AutoAwesomeRoundedIcon sx={{ fontSize: 9, color: '#c084fc' }} />
                <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: '#c084fc' }}>AI-Powered</Typography>
              </Box>
            </Box>
            <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', mt: 0.2 }}>
              Business knowledge base for your AI
            </Typography>
          </Box>

          {/* Inline stat pills */}
          <Box sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center', gap: 0.75 }}>
            {[
              { label: 'Entries', value: totalEntries, color: '#818cf8' },
              { label: 'Sources', value: totalSources, color: '#22d3ee' },
              { label: 'Avg Quality', value: avgQuality, suffix: '%', color: '#34d399' },
              { label: 'AI-Ready', value: aiReady, color: '#c084fc' },
            ].map(s => (
              <Box key={s.label} sx={{
                display: 'flex', alignItems: 'center', gap: 0.5,
                px: 1, py: 0.45, borderRadius: '8px',
                background: isDark ? alpha(s.color, 0.1) : alpha(s.color, 0.07),
                border: `1px solid ${alpha(s.color, isDark ? 0.2 : 0.15)}`,
              }}>
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 800, color: s.color, lineHeight: 1 }}>
                  <CountUp target={s.value} suffix={s.suffix || ''} />
                </Typography>
                <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>{s.label}</Typography>
              </Box>
            ))}
          </Box>
        </Box>

        {/* Right: actions */}
        <Box sx={{ display: 'flex', gap: 0.75 }}>
          <Button
            startIcon={<LinkRoundedIcon sx={{ fontSize: '14px !important' }} />}
            onClick={() => { setActiveCategory('sources'); }}
            sx={{
              fontWeight: 700, fontSize: '0.72rem', px: 1.5, py: 0.7, borderRadius: '9px',
              textTransform: 'none', flexShrink: 0,
              border: `1px solid ${isDark ? 'rgba(255,255,255,0.12)' : theme.palette.divider}`,
              color: 'text.primary', background: 'transparent',
              '&:hover': { background: isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.04) },
            }}
          >
            Sources
          </Button>
          <Button
            startIcon={<AddRoundedIcon sx={{ fontSize: '15px !important' }} />}
            onClick={() => setModalOpen(true)}
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
            Add Data
          </Button>
        </Box>
      </Box>

      {/* ── Body: left nav + right content ── */}
      <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>
        {/* Left nav — hidden on mobile */}
        <Box sx={{ display: { xs: 'none', md: 'flex' }, flexDirection: 'column', overflow: 'hidden' }}>
          <LeftNav
            entries={DATA_ENTRIES}
            activeCategory={activeCategory}
            onSelect={setActiveCategory}
            isDark={isDark}
            theme={theme}
            search={search}
            onSearch={setSearch}
          />
        </Box>

        {/* Right content */}
        <Box sx={{
          flex: 1, overflowY: 'auto', minWidth: 0,
          px: { xs: 2, sm: 2.5 }, py: 2,
          '&::-webkit-scrollbar': { width: 4 },
          '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
        }}>
          {/* Mobile search */}
          <Box sx={{ display: { xs: 'flex', md: 'none' }, mb: 1.5, alignItems: 'center', gap: 0.75,
            px: 1.25, py: 0.7, borderRadius: '10px',
            background: isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04),
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : theme.palette.divider}`,
          }}>
            <SearchRoundedIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
            <InputBase placeholder="Search data..." value={search} onChange={e => setSearch(e.target.value)}
              sx={{ fontSize: '0.75rem', color: 'text.primary', flex: 1, '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 } }} />
          </Box>

          {/* AI insight banner — shown when there are low quality entries */}
          {(() => {
            const lowCount = DATA_ENTRIES.filter(e => e.qualityScore < 75).length;
            const missingCount = DATA_ENTRIES.filter(e => e.missingFields.length > 0).length;
            if (lowCount === 0 && missingCount === 0) return null;
            return (
              <Box sx={{
                display: 'flex', alignItems: 'flex-start', gap: 1, mb: 2,
                px: 1.5, py: 1.1, borderRadius: '12px',
                background: isDark ? 'rgba(192,132,252,0.07)' : alpha('#c084fc', 0.05),
                border: `1px solid ${alpha('#c084fc', isDark ? 0.2 : 0.15)}`,
                animation: 'fadeIn 0.3s ease-out',
                '@keyframes fadeIn': { from: { opacity: 0 }, to: { opacity: 1 } },
              }}>
                <AutoAwesomeRoundedIcon sx={{ fontSize: 14, color: '#c084fc', mt: 0.1, flexShrink: 0 }} />
                <Box>
                  <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: '#c084fc', mb: 0.2 }}>AI Data Insight</Typography>
                  <Typography sx={{ fontSize: '0.7rem', color: isDark ? alpha('#c084fc', 0.8) : '#7c3aed', lineHeight: 1.5 }}>
                    {missingCount > 0 && `${missingCount} entries have missing fields. `}
                    {lowCount > 0 && `${lowCount} entries are below 75% quality. `}
                    Completing these will improve AI personalization and response accuracy.
                  </Typography>
                </Box>
              </Box>
            );
          })()}

          {/* Sources view */}
          {activeCategory === 'sources' && (
            <SourcesView isDark={isDark} theme={theme} />
          )}

          {/* All / category view */}
          {activeCategory !== 'sources' && (
            <>
              {filteredEntries.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 10 }}>
                  <StorageRoundedIcon sx={{ fontSize: 40, color: 'text.disabled', mb: 1.5 }} />
                  <Typography sx={{ fontSize: '0.88rem', color: 'text.secondary', mb: 0.5 }}>No data entries found</Typography>
                  <Typography sx={{ fontSize: '0.72rem', color: 'text.disabled', mb: 2 }}>
                    {search ? 'Try a different search term' : 'Add your first data entry to power your AI'}
                  </Typography>
                  <Button onClick={() => setModalOpen(true)} startIcon={<AddRoundedIcon />} sx={{
                    background: grad, color: '#fff', fontWeight: 700, fontSize: '0.75rem',
                    px: 2, py: 0.8, borderRadius: '9px', textTransform: 'none',
                  }}>Add Data</Button>
                </Box>
              ) : activeCategory === 'all' ? (
                // Grouped by category
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.75, pb: 4 }}>
                  {Array.from(groupedEntries.entries()).map(([cat, entries]) => (
                    <CategorySection
                      key={cat} category={cat} entries={entries}
                      isDark={isDark} theme={theme}
                      onEntryClick={setSelectedEntry}
                    />
                  ))}
                </Box>
              ) : (
                // Single category
                <Box sx={{ pb: 4 }}>
                  <CategorySection
                    category={activeCategory as DataCategory}
                    entries={filteredEntries}
                    isDark={isDark} theme={theme}
                    onEntryClick={setSelectedEntry}
                  />
                </Box>
              )}
            </>
          )}
        </Box>
      </Box>

      {/* Entry detail panel */}
      {selectedEntry && (
        <EntryPanel
          entry={selectedEntry} isDark={isDark} theme={theme}
          onClose={() => setSelectedEntry(null)}
        />
      )}

      {/* Add data modal */}
      <AddDataModal open={modalOpen} onClose={() => setModalOpen(false)} isDark={isDark} theme={theme} />
    </Box>
  );
}
