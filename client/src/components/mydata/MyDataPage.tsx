'use client';

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  Box, Typography, useTheme, alpha, InputBase,
  IconButton, Tooltip, Button, Modal, type Theme,
  CircularProgress, Snackbar, Alert,
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
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import BusinessRoundedIcon from '@mui/icons-material/BusinessRounded';
import GavelRoundedIcon from '@mui/icons-material/GavelRounded';
import SchoolRoundedIcon from '@mui/icons-material/SchoolRounded';
import SpeedRoundedIcon from '@mui/icons-material/SpeedRounded';
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { lightGradients, darkGradients } from '@/theme/palette';
import {
  CATEGORY_CONFIG, SOURCE_TYPE_CONFIG,
  SOURCE_STATUS_CONFIG, QUALITY_CONFIG, AI_RELEVANCE_CONFIG,
  getQualityLevel, type DataCategory,
} from './myDataData';
// React Query hooks
import {
  useDataStats, useDataSources, useDataEntries, useDataEntriesByCategory,
} from '@/hooks/queries/useData';
import {
  useUploadFile, useCreateManualEntry, useConnectGoogleSheet,
  useDeleteSource, useSyncSource, useDeleteEntry, useUpdateEntry,
} from '@/hooks/mutations/useDataMutations';
// API types
import type {
  DataEntry, DataSource,
} from '@/services/endpoints/data';

// ── Category icon map ─────────────────────────────────────────────────────────
const CATEGORY_ICONS: Record<DataCategory, React.ElementType> = {
  product_service:     InventoryRoundedIcon,
  pricing_payment:     PaymentsRoundedIcon,
  contact_support:     PeopleRoundedIcon,
  offers_promotions:   LocalOfferRoundedIcon,
  delivery_shipping:   LocalShippingRoundedIcon,
  company_info:        BusinessRoundedIcon,
  policies_legal:      GavelRoundedIcon,
  educational_content: SchoolRoundedIcon,
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
  const mappedStatus = status === 'active' ? 'connected' : status === 'syncing' ? 'syncing' : 'paused';
  const cfg = SOURCE_STATUS_CONFIG[mappedStatus];
  const Icon = mappedStatus === 'connected' ? CheckCircleRoundedIcon
    : mappedStatus === 'syncing' ? SyncRoundedIcon
    : PauseCircleRoundedIcon;
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.4,
      px: 0.65, py: 0.15, borderRadius: '5px',
      background: cfg.bg, border: `1px solid ${alpha(cfg.color, 0.3)}`,
    }}>
      <Icon sx={{
        fontSize: 8, color: cfg.color,
        animation: mappedStatus === 'syncing' ? 'spin 1.5s linear infinite' : 'none',
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
  entries, activeCategory, onSelect, isDark, theme, search, onSearch, sourcesCount,
}: {
  entries: DataEntry[]; activeCategory: DataCategory | 'all' | 'sources';
  onSelect: (c: DataCategory | 'all' | 'sources') => void;
  isDark: boolean; theme: Theme; search: string; onSearch: (v: string) => void;
  sourcesCount: number;
}) {
  const categories = Object.keys(CATEGORY_CONFIG) as DataCategory[];
  const countByCategory = useMemo(() => {
    const map: Record<string, number> = {};
    entries.forEach(e => { map[e.category] = (map[e.category] || 0) + 1; });
    return map;
  }, [entries]);

  const totalEntries = entries.length;
  const totalSources = sourcesCount;

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
  const catCfg  = CATEGORY_CONFIG[entry.category as DataCategory] ?? CATEGORY_CONFIG.product_service;
  const level   = getQualityLevel(entry.quality_score);
  const qualCfg = QUALITY_CONFIG[level];
  const accentColor = catCfg.color;

  // Convert structured_data record into display rows
  const fieldRows = Object.entries(entry.structured_data ?? {}).map(([key, value]) => ({
    key,
    label: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    value: String(value ?? ''),
    isUrl: /^https?:\/\//.test(String(value ?? '')),
  }));

  const missingFields = entry.missing_fields ?? [];
  const updatedAt = entry.updated_at
    ? new Date(entry.updated_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
    : '—';

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
          background: isDark ? alpha(accentColor, 0.05) : alpha(accentColor, 0.03),
        }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0 }}>
              <Box sx={{
                width: 36, height: 36, borderRadius: '10px', flexShrink: 0,
                background: alpha(accentColor, isDark ? 0.2 : 0.12),
                border: `1.5px solid ${alpha(accentColor, 0.3)}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {(() => { const Icon = CATEGORY_ICONS[entry.category as DataCategory] ?? InventoryRoundedIcon; return <Icon sx={{ fontSize: 17, color: accentColor }} />; })()}
              </Box>
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: '1rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
                  {entry.title}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.4, flexWrap: 'wrap' }}>
                  <Box sx={{ px: 0.65, py: 0.15, borderRadius: '5px', background: alpha(catCfg.color, isDark ? 0.15 : 0.1), border: `1px solid ${alpha(catCfg.color, 0.25)}` }}>
                    <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: catCfg.color }}>{catCfg.label}</Typography>
                  </Box>
                  {entry.subtype && (
                    <Box sx={{ px: 0.65, py: 0.15, borderRadius: '5px', background: isDark ? 'rgba(255,255,255,0.06)' : alpha(theme.palette.text.primary, 0.04), border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}` }}>
                      <Typography sx={{ fontSize: '0.55rem', fontWeight: 600, color: 'text.secondary' }}>{entry.subtype}</Typography>
                    </Box>
                  )}
                  <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>· {updatedAt}</Typography>
                </Box>
              </Box>
            </Box>
            <IconButton size="small" onClick={onClose} sx={{ width: 28, height: 28, borderRadius: '7px', color: 'text.secondary', flexShrink: 0, '&:hover': { background: isDark ? 'rgba(255,255,255,0.07)' : alpha(theme.palette.text.primary, 0.05) } }}>
              <CloseRoundedIcon sx={{ fontSize: 15 }} />
            </IconButton>
          </Box>
          {/* Quality */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <SpeedRoundedIcon sx={{ fontSize: 11, color: 'text.disabled' }} />
              <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>Quality</Typography>
              <QualityStrip score={entry.quality_score} isDark={isDark} />
              <Box sx={{ px: 0.55, py: 0.1, borderRadius: '5px', background: isDark ? qualCfg.darkBg : qualCfg.bg, border: `1px solid ${alpha(qualCfg.color, 0.3)}` }}>
                <Typography sx={{ fontSize: '0.52rem', fontWeight: 700, color: qualCfg.color }}>{qualCfg.label}</Typography>
              </Box>
            </Box>
          </Box>
        </Box>

        {/* Fields */}
        <Box sx={{ flex: 1, overflowY: 'auto', p: 2,
          '&::-webkit-scrollbar': { width: 4 },
          '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
        }}>
          {missingFields.length > 0 && (
            <Box sx={{
              display: 'flex', alignItems: 'flex-start', gap: 0.75, mb: 1.75,
              px: 1.25, py: 0.9, borderRadius: '10px',
              background: isDark ? 'rgba(251,191,36,0.07)' : 'rgba(251,191,36,0.05)',
              border: `1px solid ${isDark ? 'rgba(251,191,36,0.2)' : 'rgba(251,191,36,0.18)'}`,
            }}>
              <WarningAmberRoundedIcon sx={{ fontSize: 13, color: '#fbbf24', mt: 0.1, flexShrink: 0 }} />
              <Typography sx={{ fontSize: '0.7rem', color: isDark ? alpha('#fbbf24', 0.9) : '#b45309', lineHeight: 1.5 }}>
                Missing fields: {missingFields.join(', ')} — adding these will improve AI accuracy.
              </Typography>
            </Box>
          )}

          {/* Field rows from structured_data */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {fieldRows.map((field, i) => (
              <Box key={field.key} sx={{
                display: 'grid', gridTemplateColumns: '160px 1fr',
                alignItems: 'flex-start', gap: 1,
                py: 0.9, px: 0.5,
                borderBottom: i < fieldRows.length - 1
                  ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : theme.palette.divider}`
                  : 'none',
                '&:hover': { background: isDark ? 'rgba(255,255,255,0.02)' : alpha(theme.palette.text.primary, 0.015), borderRadius: '6px' },
                transition: 'background 0.12s ease',
              }}>
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: 'text.secondary', pt: 0.1 }}>
                  {field.label}
                </Typography>
                {field.isUrl ? (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                    <Typography sx={{ fontSize: '0.75rem', color: isDark ? '#818cf8' : theme.palette.primary.main, fontWeight: 500, wordBreak: 'break-all' }}>
                      {field.value}
                    </Typography>
                    <OpenInNewRoundedIcon sx={{ fontSize: 11, color: isDark ? '#818cf8' : theme.palette.primary.main, flexShrink: 0 }} />
                  </Box>
                ) : (
                  <Typography sx={{ fontSize: '0.75rem', color: 'text.primary', fontWeight: 500, lineHeight: 1.5 }}>
                    {field.value}
                  </Typography>
                )}
              </Box>
            ))}
            {fieldRows.length === 0 && (
              <Typography sx={{ fontSize: '0.72rem', color: 'text.disabled', py: 2, textAlign: 'center' }}>
                No structured data available.
              </Typography>
            )}
          </Box>

          {/* AI tags */}
          {(entry.ai_tags ?? []).length > 0 && (
            <Box sx={{ mt: 1.5, pt: 1.5, borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}` }}>
              <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.08em', mb: 0.75 }}>AI Tags</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {(entry.ai_tags ?? []).map(tag => (
                  <Box key={tag} sx={{ px: 0.75, py: 0.25, borderRadius: '6px', background: isDark ? 'rgba(129,140,248,0.1)' : alpha('#818cf8', 0.07), border: `1px solid ${alpha('#818cf8', 0.2)}` }}>
                    <Typography sx={{ fontSize: '0.6rem', fontWeight: 600, color: '#818cf8' }}>{tag}</Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          )}
        </Box>

        {/* Footer actions */}
        <Box sx={{
          px: 2.5, py: 1.5,
          borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
          display: 'flex', gap: 0.75, justifyContent: 'flex-end',
        }}>
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
  const catCfg    = CATEGORY_CONFIG[entry.category as DataCategory] ?? CATEGORY_CONFIG.product_service;
  const level     = getQualityLevel(entry.quality_score);
  const qualColor = QUALITY_CONFIG[level].color;
  const Icon      = CATEGORY_ICONS[entry.category as DataCategory] ?? InventoryRoundedIcon;
  const preview   = Object.values(entry.structured_data ?? {}).find(v => v) ?? '—';
  const updatedAt = entry.updated_at
    ? new Date(entry.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '—';

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
      '&:hover': { background: isDark ? 'rgba(255,255,255,0.025)' : alpha(theme.palette.text.primary, 0.02) },
      animation: `rowIn 0.22s ease-out ${index * 0.04}s both`,
      '@keyframes rowIn': { from: { opacity: 0, transform: 'translateX(-4px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
    }}>
      <Box sx={{
        width: 26, height: 26, borderRadius: '7px', flexShrink: 0,
        background: alpha(catCfg.color, isDark ? 0.15 : 0.1),
        border: `1px solid ${alpha(catCfg.color, 0.2)}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon sx={{ fontSize: 13, color: catCfg.color }} />
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontSize: '0.8rem', fontWeight: 700, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', lineHeight: 1.3 }}>
          {entry.title}
        </Typography>
        <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', mt: 0.15 }}>
          {preview}
        </Typography>
      </Box>
      <Box sx={{ px: 0.65, py: 0.2, borderRadius: '5px', background: alpha(catCfg.color, isDark ? 0.12 : 0.08), border: `1px solid ${alpha(catCfg.color, 0.2)}`, display: 'inline-flex', alignSelf: 'center' }}>
        <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: catCfg.color }}>{catCfg.label}</Typography>
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Box sx={{ width: 32, height: 3, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)', overflow: 'hidden' }}>
          <Box sx={{ height: '100%', borderRadius: 2, width: `${entry.quality_score}%`, background: qualColor }} />
        </Box>
        <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: qualColor }}>{entry.quality_score}%</Typography>
      </Box>
      <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>—</Typography>
      <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', textAlign: 'right' }}>{updatedAt}</Typography>
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
  const avgQuality = Math.round(entries.reduce((s, e) => s + e.quality_score, 0) / entries.length);
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
  const { data: sourcesData, isLoading } = useDataSources();
  const deleteSource = useDeleteSource();
  const syncSource   = useSyncSource();

  const sources      = sourcesData?.sources ?? [];
  const totalRecords = sourcesData?.total_records ?? 0;

  const handleSync = (id: string) => syncSource.mutate(id);
  const handleDelete = (id: string) => deleteSource.mutate(id);

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
            <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: '#22d3ee' }}>{sources.length} connected</Typography>
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
          display: 'grid', gridTemplateColumns: '1fr 100px 80px 90px 80px 96px',
          alignItems: 'center', gap: 1.5, px: 1.75, py: 0.75,
          background: isDark ? 'rgba(255,255,255,0.03)' : alpha(theme.palette.text.primary, 0.02),
          borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
        }}>
          {['Source', 'Type', 'Records', 'AI-Ready', 'Status', 'Actions'].map(h => (
            <Typography key={h} sx={{ fontSize: '0.58rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
              {h}
            </Typography>
          ))}
        </Box>

        {sources.map((src, i) => {
          const typeCfg = SOURCE_TYPE_CONFIG[src.source_type as keyof typeof SOURCE_TYPE_CONFIG] ?? { label: src.source_type, color: '#818cf8' };
          const aiPct   = src.total_records > 0 ? Math.round((src.ai_ready_count / src.total_records) * 100) : 0;
          const aiColor = aiPct >= 75 ? '#34d399' : aiPct >= 50 ? '#fbbf24' : '#f87171';
          const isSyncing = src.status === 'syncing' || syncSource.isPending;
          const isDeleting = deleteSource.isPending && deleteSource.variables === src.id;
          const lastSync = src.last_sync_at
            ? new Date(src.last_sync_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : 'Never';
          return (
            <Box key={src.id} sx={{
              display: 'grid', gridTemplateColumns: '1fr 100px 80px 90px 80px 96px',
              alignItems: 'center', gap: 1.5, px: 1.75, py: 1.1,
              borderBottom: i < sources.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : theme.palette.divider}` : 'none',
              transition: 'all 0.25s ease',
              opacity: isDeleting ? 0 : 1,
              transform: isDeleting ? 'translateX(12px)' : 'none',
              '&:hover': { background: isDark ? 'rgba(255,255,255,0.025)' : alpha(theme.palette.text.primary, 0.02) },
              animation: `rowIn 0.22s ease-out ${i * 0.05}s both`,
              '@keyframes rowIn': { from: { opacity: 0, transform: 'translateX(-4px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
            }}>
              <Box>
                <Typography sx={{ fontSize: '0.8rem', fontWeight: 700, color: 'text.primary' }}>{src.name}</Typography>
                <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', mt: 0.1 }}>Last sync: {lastSync}</Typography>
              </Box>
              <Box sx={{ px: 0.65, py: 0.2, borderRadius: '5px', background: alpha(typeCfg.color, isDark ? 0.12 : 0.08), border: `1px solid ${alpha(typeCfg.color, 0.2)}`, display: 'inline-flex', alignSelf: 'center' }}>
                <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: typeCfg.color }}>{typeCfg.label}</Typography>
              </Box>
              <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: 'text.primary' }}>{src.total_records.toLocaleString()}</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6 }}>
                <Box sx={{ flex: 1, height: 3, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)', overflow: 'hidden' }}>
                  <Box sx={{ height: '100%', borderRadius: 2, width: `${aiPct}%`, background: aiColor, transition: 'width 0.9s ease' }} />
                </Box>
                <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: aiColor, minWidth: 26 }}>{aiPct}%</Typography>
              </Box>
              <SourcePill status={src.status} />
              {/* Action buttons */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                <Tooltip title="Sync now" placement="top">
                  <IconButton
                    size="small"
                    onClick={() => handleSync(src.id)}
                    disabled={isSyncing || src.status === 'paused'}
                    sx={{
                      width: 26, height: 26, borderRadius: '7px',
                      color: '#60a5fa',
                      border: `1px solid ${alpha('#60a5fa', 0.25)}`,
                      background: alpha('#60a5fa', isDark ? 0.08 : 0.05),
                      '&:hover': { background: alpha('#60a5fa', 0.15) },
                      '&:disabled': { opacity: 0.4 },
                    }}
                  >
                    <SyncRoundedIcon sx={{
                      fontSize: 13,
                      animation: isSyncing ? 'spin 1.5s linear infinite' : 'none',
                      '@keyframes spin': { from: { transform: 'rotate(0deg)' }, to: { transform: 'rotate(360deg)' } },
                    }} />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Remove source" placement="top">
                  <IconButton
                    size="small"
                    onClick={() => handleDelete(src.id)}
                    disabled={deleteSource.isPending}
                    sx={{
                      width: 26, height: 26, borderRadius: '7px',
                      color: '#f87171',
                      border: `1px solid ${alpha('#f87171', 0.25)}`,
                      background: alpha('#f87171', isDark ? 0.08 : 0.05),
                      '&:hover': { background: alpha('#f87171', 0.15) },
                    }}
                  >
                    <DeleteOutlineRoundedIcon sx={{ fontSize: 13 }} />
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>
          );
        })}

        {sources.length === 0 && (
          <Box sx={{ px: 1.75, py: 3, textAlign: 'center' }}>
            <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>No sources connected. Add one using the "Add Data" button.</Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}

// ── Add data modal ────────────────────────────────────────────────────────────
// Flow: category (mandatory) → method (csv/manual/sheets/api) → form
// REDESIGNED: no right column, guide appears as smooth hover tooltip on each card
function AddDataModal({ open, onClose, isDark, theme }: {
  open: boolean; onClose: () => void; isDark: boolean; theme: Theme;
}) {
  type Step = 'category' | 'method' | 'csv' | 'manual' | 'sheets' | 'api';
  const [step, setStep] = useState<Step>('category');
  const [selectedCategory, setSelectedCategory] = useState<DataCategory | null>(null);
  const [hoveredCat, setHoveredCat] = useState<DataCategory | null>(null);
  const [tooltipAnchor, setTooltipAnchor] = useState<{ top: number; left: number; width: number; flipUp: boolean } | null>(null);
  const cardRefs = useRef<Partial<Record<DataCategory, HTMLElement>>>({});

  // Form state
  const [csvFile, setCsvFile]           = useState<File | null>(null);
  const [sourceName, setSourceName]     = useState('');
  const [manualTitle, setManualTitle]   = useState('');
  const [manualContent, setManualContent] = useState('');
  const [sheetUrl, setSheetUrl]         = useState('');
  const [sheetName, setSheetName]       = useState('');
  const [sheetSourceName, setSheetSourceName] = useState('');

  // Mutations
  const uploadFile      = useUploadFile();
  const createManual    = useCreateManualEntry();
  const connectSheet    = useConnectGoogleSheet();

  const isSubmitting = uploadFile.isPending || createManual.isPending || connectSheet.isPending;

  const allCategories = Object.keys(CATEGORY_CONFIG) as DataCategory[];

  const methods = [
    { id: 'csv' as const,    icon: UploadFileRoundedIcon, label: 'Upload CSV / Excel', desc: 'Import rows from a file',       color: '#34d399' },
    { id: 'manual' as const, icon: EditRoundedIcon,       label: 'Manual Entry',       desc: 'Type data fields directly',    color: '#c084fc' },
    { id: 'sheets' as const, icon: TableChartRoundedIcon, label: 'Google Sheets',      desc: 'Sync live from a spreadsheet', color: '#60a5fa' },
    { id: 'api' as const,    icon: ApiRoundedIcon,        label: 'API / Webhook',      desc: 'Connect via REST endpoint',    color: '#22d3ee' },
  ];

  const inputSx = {
    px: 1.5, py: 1, borderRadius: '10px', fontSize: '0.82rem',
    color: 'text.primary',
    background: isDark ? 'rgba(255,255,255,0.04)' : alpha(theme.palette.text.primary, 0.03),
    border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : theme.palette.divider}`,
    '& input::placeholder': { color: theme.palette.text.disabled, opacity: 1 },
    '&:focus-within': { borderColor: isDark ? 'rgba(129,140,248,0.6)' : alpha(theme.palette.primary.main, 0.5), boxShadow: isDark ? '0 0 0 3px rgba(129,140,248,0.1)' : `0 0 0 3px ${alpha(theme.palette.primary.main, 0.08)}` },
    transition: 'border-color 0.18s ease, box-shadow 0.18s ease',
  };

  const handleClose = () => {
    onClose();
    setStep('category');
    setSelectedCategory(null);
    setHoveredCat(null);
    setTooltipAnchor(null);
    setCsvFile(null);
    setSourceName('');
    setManualTitle('');
    setManualContent('');
    setSheetUrl('');
    setSheetName('');
    setSheetSourceName('');
  };

  const handleBack = () => {
    if (step === 'method') { setStep('category'); setSelectedCategory(null); }
    else if (['csv', 'manual', 'sheets', 'api'].includes(step)) setStep('method');
  };

  const headerTitle: Record<Step, string> = {
    category: 'Add Business Data',
    method:   'How do you want to add data?',
    csv:      'Upload CSV / Excel',
    manual:   'Manual Entry',
    sheets:   'Connect Google Sheets',
    api:      'API / Webhook',
  };

  return (
    <Modal
      open={open}
      onClose={handleClose}
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: { xs: 1.5, sm: 2 },
      }}
    >
      <Box sx={{
        width: '100%',
        maxWidth: 520,
        borderRadius: '20px',
        background: isDark ? '#0d1526' : '#ffffff',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.09)' : 'rgba(0,0,0,0.08)'}`,
        boxShadow: isDark
          ? '0 40px 100px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.04)'
          : '0 40px 100px rgba(15,23,42,0.18), 0 0 0 1px rgba(0,0,0,0.04)',
        overflow: 'hidden',
        outline: 'none',
        animation: 'modalSlideIn 0.24s cubic-bezier(0.34,1.56,0.64,1)',
        '@keyframes modalSlideIn': {
          from: { opacity: 0, transform: 'scale(0.94) translateY(12px)' },
          to:   { opacity: 1, transform: 'scale(1) translateY(0)' },
        },
      }}>

        {/* ── Header ── */}
        <Box sx={{
          px: 3, pt: 2.5, pb: 2,
          borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1,
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0 }}>
            {step !== 'category' && (
              <IconButton
                size="small"
                onClick={handleBack}
                sx={{
                  width: 30, height: 30, borderRadius: '8px', flexShrink: 0,
                  color: 'text.secondary',
                  background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
                  '&:hover': { background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)', color: 'text.primary' },
                  transition: 'all 0.15s ease',
                }}
              >
                <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, lineHeight: 1 }}>←</Typography>
              </IconButton>
            )}
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontSize: '1rem', fontWeight: 800, color: 'text.primary', letterSpacing: '-0.025em', lineHeight: 1.2 }}>
                {headerTitle[step]}
              </Typography>
              <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', mt: 0.25, lineHeight: 1.4 }}>
                {step === 'category'
                  ? 'Choose a category — required before adding any data'
                  : selectedCategory
                    ? `${CATEGORY_CONFIG[selectedCategory].emoji} ${CATEGORY_CONFIG[selectedCategory].label}`
                    : 'Fill in the details below'}
              </Typography>
            </Box>
          </Box>
          <IconButton
            size="small"
            onClick={handleClose}
            sx={{
              width: 30, height: 30, borderRadius: '8px', flexShrink: 0,
              color: 'text.secondary',
              background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
              '&:hover': { background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)', color: 'text.primary' },
              transition: 'all 0.15s ease',
            }}
          >
            <CloseRoundedIcon sx={{ fontSize: 15 }} />
          </IconButton>
        </Box>

        {/* ── Step: Category selection ── */}
        {step === 'category' && (
          <Box sx={{ p: { xs: 1.75, sm: 2.5 }, display: 'flex', flexDirection: 'column', gap: { xs: 1.5, sm: 2 } }}>
            {/* Required label */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: '#ef4444', flexShrink: 0 }} />
              <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                Required — select one
              </Typography>
            </Box>

            {/* Category grid — 2 equal columns, fixed-height cards so all are uniform */}
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, position: 'relative' }}>
              {allCategories.map(cat => {
                const cfg = CATEGORY_CONFIG[cat];
                const Icon = CATEGORY_ICONS[cat];
                const isSelected = selectedCategory === cat;
                const isHovered = hoveredCat === cat;
                return (
                  <Box key={cat} sx={{ position: 'relative' }}>
                    {/* Card — fixed height, vertical layout: icon top-left, label bottom */}
                    <Box
                      component="button"
                      ref={(el: HTMLElement | null) => { if (el) cardRefs.current[cat] = el; }}
                      onClick={() => setSelectedCategory(cat)}
                      onMouseEnter={() => {
                        const el = cardRefs.current[cat];
                        if (el) {
                          const rect = el.getBoundingClientRect();
                          const TOOLTIP_HEIGHT = 200; // estimated max tooltip height
                          const spaceBelow = window.innerHeight - rect.bottom;
                          const flipUp = spaceBelow < TOOLTIP_HEIGHT + 20;
                          setTooltipAnchor({
                            top: flipUp ? rect.top - TOOLTIP_HEIGHT - 10 : rect.bottom + 10,
                            left: rect.left + rect.width / 2,
                            width: rect.width,
                            flipUp,
                          });
                        }
                        setHoveredCat(cat);
                      }}
                      onMouseLeave={() => { setHoveredCat(null); setTooltipAnchor(null); }}
                      sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'flex-start',
                        justifyContent: 'space-between',
                        px: 1.25,
                        py: 1.1,
                        // fixed height — every card identical regardless of label length
                        height: 76,
                        borderRadius: '12px',
                        cursor: 'pointer',
                        textAlign: 'left',
                        width: '100%',
                        background: isSelected
                          ? isDark ? alpha(cfg.color, 0.16) : alpha(cfg.color, 0.09)
                          : isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.025)',
                        border: `1.5px solid ${isSelected
                          ? cfg.color
                          : isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
                        transition: 'all 0.18s cubic-bezier(0.4,0,0.2,1)',
                        '&:hover': {
                          background: isDark ? alpha(cfg.color, 0.13) : alpha(cfg.color, 0.08),
                          borderColor: alpha(cfg.color, 0.65),
                          transform: 'translateY(-1px)',
                          boxShadow: isDark
                            ? `0 6px 20px ${alpha(cfg.color, 0.18)}`
                            : `0 6px 20px ${alpha(cfg.color, 0.14)}`,
                        },
                        '&:active': { transform: 'translateY(0)' },
                      }}
                    >
                      {/* Top row: icon + optional checkmark */}
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                        <Box sx={{
                          width: 28, height: 28, borderRadius: '8px', flexShrink: 0,
                          background: alpha(cfg.color, isDark ? 0.2 : 0.13),
                          border: `1px solid ${alpha(cfg.color, 0.28)}`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                          <Icon sx={{ fontSize: 14, color: cfg.color }} />
                        </Box>
                        {isSelected && (
                          <CheckCircleRoundedIcon sx={{ fontSize: 14, color: cfg.color }} />
                        )}
                      </Box>

                      {/* Label — hard-clamped to 2 lines, never causes height growth */}
                      <Typography sx={{
                        fontSize: '0.68rem',
                        fontWeight: isSelected ? 700 : 600,
                        color: isSelected ? cfg.color : 'text.primary',
                        lineHeight: 1.3,
                        width: '100%',
                        textAlign: 'left',
                        transition: 'color 0.15s ease',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}>
                        {cfg.emoji} {cfg.label}
                      </Typography>
                    </Box>

                    {/* Guide tooltip — fixed position, flips above card when near bottom of viewport */}
                    {isHovered && tooltipAnchor && (
                      <Box sx={{
                        position: 'fixed',
                        top: tooltipAnchor.top,
                        left: tooltipAnchor.left,
                        transform: 'translateX(-50%)',
                        width: 260,
                        zIndex: 99999,
                        borderRadius: '14px',
                        background: isDark ? '#1a2540' : '#ffffff',
                        border: `1.5px solid ${alpha(cfg.color, 0.5)}`,
                        boxShadow: isDark
                          ? `0 20px 50px rgba(0,0,0,0.75), 0 0 0 1px ${alpha(cfg.color, 0.2)}`
                          : `0 20px 50px rgba(15,23,42,0.2), 0 0 0 1px ${alpha(cfg.color, 0.12)}`,
                        p: 1.75,
                        animation: 'guideIn 0.2s cubic-bezier(0.34,1.56,0.64,1)',
                        '@keyframes guideIn': {
                          from: { opacity: 0, transform: `translateX(-50%) translateY(${tooltipAnchor.flipUp ? '-6px' : '6px'}) scale(0.95)` },
                          to:   { opacity: 1, transform: 'translateX(-50%) translateY(0) scale(1)' },
                        },
                        // arrow — points down when flipped up, points up when below
                        '&::before': {
                          content: '""',
                          position: 'absolute',
                          ...(tooltipAnchor.flipUp
                            ? {
                                bottom: -7,
                                top: 'auto',
                                left: '50%',
                                transform: 'translateX(-50%) rotate(225deg)',
                              }
                            : {
                                top: -7,
                                left: '50%',
                                transform: 'translateX(-50%) rotate(45deg)',
                              }
                          ),
                          width: 12,
                          height: 12,
                          background: isDark ? '#1a2540' : '#ffffff',
                          border: `1.5px solid ${alpha(cfg.color, 0.5)}`,
                          borderRight: 'none',
                          borderBottom: 'none',
                        },
                      }}>
                        {/* Guide header */}
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1 }}>
                          <Box sx={{
                            width: 24, height: 24, borderRadius: '7px', flexShrink: 0,
                            background: alpha(cfg.color, isDark ? 0.22 : 0.14),
                            border: `1px solid ${alpha(cfg.color, 0.3)}`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                          }}>
                            <Icon sx={{ fontSize: 13, color: cfg.color }} />
                          </Box>
                          <Typography sx={{ fontSize: '0.7rem', fontWeight: 800, color: cfg.color, lineHeight: 1.2 }}>
                            {cfg.emoji} {cfg.label}
                          </Typography>
                        </Box>

                        {/* Guide text */}
                        <Typography sx={{
                          fontSize: '0.64rem',
                          color: isDark ? 'rgba(203,213,225,0.85)' : 'rgba(30,41,59,0.75)',
                          lineHeight: 1.65,
                          mb: 1.1,
                        }}>
                          {cfg.guide}
                        </Typography>

                        {/* Example column tags */}
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {cfg.exampleColumns.slice(0, 5).map(col => (
                            <Box key={col} sx={{
                              px: 0.8, py: 0.3, borderRadius: '6px',
                              background: alpha(cfg.color, isDark ? 0.18 : 0.1),
                              border: `1px solid ${alpha(cfg.color, 0.32)}`,
                            }}>
                              <Typography sx={{ fontSize: '0.58rem', fontWeight: 600, color: cfg.color, lineHeight: 1.4 }}>
                                {col}
                              </Typography>
                            </Box>
                          ))}
                        </Box>
                      </Box>
                    )}
                  </Box>
                );
              })}
            </Box>

            {/* Continue button */}
            <Box
              component="button"
              onClick={() => { if (selectedCategory) setStep('method'); }}
              disabled={!selectedCategory}
              sx={{
                width: '100%',
                border: 'none',
                cursor: selectedCategory ? 'pointer' : 'not-allowed',
                py: 1.15,
                borderRadius: '12px',
                fontWeight: 700,
                fontSize: '0.82rem',
                letterSpacing: '-0.01em',
                background: selectedCategory
                  ? `linear-gradient(135deg, ${CATEGORY_CONFIG[selectedCategory].color} 0%, ${alpha(CATEGORY_CONFIG[selectedCategory].color, 0.72)} 100%)`
                  : isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                color: selectedCategory ? '#fff' : isDark ? 'rgba(255,255,255,0.22)' : 'rgba(0,0,0,0.22)',
                transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
                boxShadow: selectedCategory
                  ? `0 4px 18px ${alpha(CATEGORY_CONFIG[selectedCategory].color, 0.38)}`
                  : 'none',
                '&:hover': {
                  opacity: selectedCategory ? 0.9 : 1,
                  transform: selectedCategory ? 'translateY(-1px)' : 'none',
                  boxShadow: selectedCategory
                    ? `0 8px 26px ${alpha(CATEGORY_CONFIG[selectedCategory].color, 0.44)}`
                    : 'none',
                },
                '&:active': { transform: 'translateY(0)' },
              }}
            >
              {selectedCategory
                ? `Continue with ${CATEGORY_CONFIG[selectedCategory].emoji} ${CATEGORY_CONFIG[selectedCategory].label}`
                : 'Select a category to continue'}
            </Box>
          </Box>
        )}

        {/* ── Step: Method selection ── */}
        {step === 'method' && (
          <Box sx={{ p: 2.5, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.25 }}>
            {methods.map(m => (
              <Box
                key={m.id}
                component="button"
                onClick={() => setStep(m.id)}
                sx={{
                  display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 1,
                  p: 1.75, borderRadius: '14px', cursor: 'pointer', textAlign: 'left',
                  background: isDark ? alpha(m.color, 0.07) : alpha(m.color, 0.05),
                  border: `1.5px solid ${alpha(m.color, isDark ? 0.18 : 0.13)}`,
                  transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
                  '&:hover': {
                    transform: 'translateY(-2px)',
                    background: isDark ? alpha(m.color, 0.13) : alpha(m.color, 0.09),
                    borderColor: alpha(m.color, 0.7),
                    boxShadow: isDark ? `0 8px 28px ${alpha(m.color, 0.2)}` : `0 8px 28px ${alpha(m.color, 0.15)}`,
                  },
                  '&:active': { transform: 'translateY(0)', transition: 'transform 0.08s ease' },
                }}
              >
                <Box sx={{
                  width: 36, height: 36, borderRadius: '10px',
                  background: alpha(m.color, 0.15),
                  border: `1px solid ${alpha(m.color, 0.25)}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <m.icon sx={{ fontSize: 18, color: m.color }} />
                </Box>
                <Box>
                  <Typography sx={{ fontSize: '0.8rem', fontWeight: 700, color: 'text.primary', lineHeight: 1.2 }}>{m.label}</Typography>
                  <Typography sx={{ fontSize: '0.65rem', color: 'text.secondary', mt: 0.3, lineHeight: 1.4 }}>{m.desc}</Typography>
                </Box>
              </Box>
            ))}
          </Box>
        )}

        {/* ── Step: CSV upload ── */}
        {step === 'csv' && selectedCategory && (
          <Box sx={{ p: 2.5, display: 'flex', flexDirection: 'column', gap: 1.75 }}>
            <CategoryBadge cat={selectedCategory} isDark={isDark} theme={theme} />
            <Box
              component="label"
              sx={{
                border: `2px dashed ${csvFile ? '#34d399' : isDark ? 'rgba(52,211,153,0.35)' : 'rgba(52,211,153,0.45)'}`,
                borderRadius: '14px', p: 3.5, textAlign: 'center', cursor: 'pointer',
                background: isDark ? 'rgba(52,211,153,0.04)' : 'rgba(52,211,153,0.03)',
                transition: 'all 0.2s ease',
                '&:hover': { background: isDark ? 'rgba(52,211,153,0.09)' : 'rgba(52,211,153,0.07)', borderColor: '#34d399' },
              }}
            >
              <input type="file" accept=".csv,.xlsx,.xls" hidden onChange={e => { const f = e.target.files?.[0]; if (f) { setCsvFile(f); setSourceName(prev => prev || f.name.replace(/\.[^.]+$/, '')); } }} />
              <UploadFileRoundedIcon sx={{ fontSize: 32, color: '#34d399', mb: 1 }} />
              <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, color: 'text.primary', mb: 0.4 }}>
                {csvFile ? csvFile.name : 'Drop CSV or Excel file here'}
              </Typography>
              <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary' }}>
                {csvFile ? `${(csvFile.size / 1024).toFixed(1)} KB` : 'or click to browse · Max 10 MB'}
              </Typography>
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 600, color: 'text.secondary', mb: 0.6 }}>Source Name</Typography>
              <InputBase value={sourceName} onChange={e => setSourceName(e.target.value)} placeholder="e.g. Product Catalog Q4" sx={inputSx} fullWidth />
            </Box>
            <Box sx={{ px: 1.5, py: 1.1, borderRadius: '10px', background: isDark ? 'rgba(52,211,153,0.06)' : 'rgba(52,211,153,0.04)', border: `1px solid ${alpha('#34d399', 0.2)}` }}>
              <Typography sx={{ fontSize: '0.63rem', color: isDark ? '#34d399' : '#059669', fontWeight: 600, mb: 0.35 }}>Suggested columns for this category</Typography>
              <Typography sx={{ fontSize: '0.61rem', color: 'text.secondary', lineHeight: 1.55 }}>
                {CATEGORY_CONFIG[selectedCategory].exampleColumns.join(' · ')}
              </Typography>
            </Box>
            <Box
              component="button"
              disabled={!csvFile || isSubmitting}
              onClick={() => {
                if (!csvFile || !selectedCategory) return;
                uploadFile.mutate(
                  { file: csvFile, sourceName: sourceName || csvFile.name, category: selectedCategory },
                  { onSuccess: handleClose },
                );
              }}
              sx={{ width: '100%', border: 'none', cursor: csvFile ? 'pointer' : 'not-allowed', py: 1.1, borderRadius: '12px', background: csvFile ? 'linear-gradient(135deg, #34d399, #22d3ee)' : isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)', color: csvFile ? '#fff' : 'text.disabled', fontSize: '0.82rem', fontWeight: 700, transition: 'all 0.18s ease', boxShadow: csvFile ? '0 4px 16px rgba(52,211,153,0.3)' : 'none', '&:hover': { opacity: csvFile ? 0.9 : 1 }, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}
            >
              {isSubmitting ? <CircularProgress size={14} sx={{ color: '#fff' }} /> : null}
              {isSubmitting ? 'Uploading…' : 'Upload & Import'}
            </Box>
          </Box>
        )}

        {/* ── Step: Manual entry ── */}
        {step === 'manual' && selectedCategory && (
          <Box sx={{ p: 2.5, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <CategoryBadge cat={selectedCategory} isDark={isDark} theme={theme} />
            <Box>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 600, color: 'text.secondary', mb: 0.6 }}>Entry Title</Typography>
              <InputBase value={manualTitle} onChange={e => setManualTitle(e.target.value)} placeholder={`e.g. ${CATEGORY_CONFIG[selectedCategory].exampleColumns[0] ?? 'Entry name'}...`} sx={inputSx} fullWidth />
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 600, color: 'text.secondary', mb: 0.6 }}>Data Content</Typography>
              <InputBase
                value={manualContent}
                onChange={e => setManualContent(e.target.value)}
                placeholder={`Describe the data — e.g. ${CATEGORY_CONFIG[selectedCategory].exampleEntry}`}
                multiline rows={4}
                sx={{ ...inputSx, alignItems: 'flex-start', '& textarea': { resize: 'none' } }}
                fullWidth
              />
            </Box>
            <Box sx={{ px: 1.5, py: 1, borderRadius: '10px', background: isDark ? alpha(CATEGORY_CONFIG[selectedCategory].color, 0.06) : alpha(CATEGORY_CONFIG[selectedCategory].color, 0.04), border: `1px solid ${alpha(CATEGORY_CONFIG[selectedCategory].color, 0.2)}` }}>
              <Typography sx={{ fontSize: '0.63rem', color: CATEGORY_CONFIG[selectedCategory].color, fontWeight: 600, mb: 0.3 }}>Suggested fields</Typography>
              <Typography sx={{ fontSize: '0.61rem', color: 'text.secondary', lineHeight: 1.55 }}>
                {CATEGORY_CONFIG[selectedCategory].exampleColumns.join(' · ')}
              </Typography>
            </Box>
            <Box
              component="button"
              disabled={!manualTitle.trim() || !manualContent.trim() || isSubmitting}
              onClick={() => {
                if (!manualTitle.trim() || !selectedCategory) return;
                createManual.mutate(
                  {
                    title:    manualTitle.trim(),
                    category: selectedCategory,
                    fields:   [{ key: 'content', label: 'Content', value: manualContent.trim() }],
                  },
                  { onSuccess: handleClose },
                );
              }}
              sx={{ width: '100%', border: 'none', cursor: manualTitle.trim() ? 'pointer' : 'not-allowed', py: 1.1, borderRadius: '12px', background: manualTitle.trim() ? 'linear-gradient(135deg, #c084fc, #818cf8)' : isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)', color: manualTitle.trim() ? '#fff' : 'text.disabled', fontSize: '0.82rem', fontWeight: 700, transition: 'all 0.18s ease', boxShadow: manualTitle.trim() ? '0 4px 16px rgba(192,132,252,0.3)' : 'none', '&:hover': { opacity: manualTitle.trim() ? 0.9 : 1 }, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}
            >
              {isSubmitting ? <CircularProgress size={14} sx={{ color: '#fff' }} /> : null}
              {isSubmitting ? 'Saving…' : 'Save Entry'}
            </Box>
          </Box>
        )}

        {/* ── Step: Google Sheets ── */}
        {step === 'sheets' && selectedCategory && (
          <Box sx={{ p: 2.5, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <CategoryBadge cat={selectedCategory} isDark={isDark} theme={theme} />
            <Box>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 600, color: 'text.secondary', mb: 0.6 }}>Source Name</Typography>
              <InputBase value={sheetSourceName} onChange={e => setSheetSourceName(e.target.value)} placeholder="e.g. Product Sheet" sx={inputSx} fullWidth />
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 600, color: 'text.secondary', mb: 0.6 }}>Google Sheets URL</Typography>
              <InputBase value={sheetUrl} onChange={e => setSheetUrl(e.target.value)} placeholder="https://docs.google.com/spreadsheets/d/..." sx={inputSx} fullWidth />
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 600, color: 'text.secondary', mb: 0.6 }}>Sheet Name (optional)</Typography>
              <InputBase value={sheetName} onChange={e => setSheetName(e.target.value)} placeholder="Sheet1" sx={inputSx} fullWidth />
            </Box>
            <Box sx={{ px: 1.5, py: 1, borderRadius: '10px', background: isDark ? 'rgba(96,165,250,0.07)' : 'rgba(96,165,250,0.05)', border: `1px solid ${alpha('#60a5fa', 0.2)}` }}>
              <Typography sx={{ fontSize: '0.63rem', color: isDark ? '#60a5fa' : '#0891b2', fontWeight: 600, mb: 0.3 }}>Suggested columns for this category</Typography>
              <Typography sx={{ fontSize: '0.61rem', color: 'text.secondary', lineHeight: 1.55 }}>
                {CATEGORY_CONFIG[selectedCategory].exampleColumns.join(' · ')}
              </Typography>
            </Box>
            <Box
              component="button"
              disabled={!sheetUrl.trim() || !sheetSourceName.trim() || isSubmitting}
              onClick={() => {
                if (!sheetUrl.trim() || !sheetSourceName.trim() || !selectedCategory) return;
                connectSheet.mutate(
                  { name: sheetSourceName.trim(), sheet_url: sheetUrl.trim(), sheet_name: sheetName.trim() || undefined, category: selectedCategory },
                  { onSuccess: handleClose },
                );
              }}
              sx={{ width: '100%', border: 'none', cursor: sheetUrl.trim() ? 'pointer' : 'not-allowed', py: 1.1, borderRadius: '12px', background: sheetUrl.trim() ? 'linear-gradient(135deg, #60a5fa, #22d3ee)' : isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)', color: sheetUrl.trim() ? '#fff' : 'text.disabled', fontSize: '0.82rem', fontWeight: 700, transition: 'all 0.18s ease', boxShadow: sheetUrl.trim() ? '0 4px 16px rgba(96,165,250,0.3)' : 'none', '&:hover': { opacity: sheetUrl.trim() ? 0.9 : 1 }, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}
            >
              {isSubmitting ? <CircularProgress size={14} sx={{ color: '#fff' }} /> : null}
              {isSubmitting ? 'Connecting…' : 'Connect Sheet'}
            </Box>
          </Box>
        )}

        {/* ── Step: API / Webhook ── */}
        {step === 'api' && selectedCategory && (
          <Box sx={{ p: 2.5, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <CategoryBadge cat={selectedCategory} isDark={isDark} theme={theme} />
            <Box>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 600, color: 'text.secondary', mb: 0.6 }}>Source Name</Typography>
              <InputBase placeholder={`e.g. ${CATEGORY_CONFIG[selectedCategory].label} API`} sx={inputSx} fullWidth />
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 600, color: 'text.secondary', mb: 0.6 }}>Endpoint URL</Typography>
              <InputBase placeholder="https://api.yoursource.com/data" sx={inputSx} fullWidth />
            </Box>
            <Box sx={{ px: 1.5, py: 1, borderRadius: '10px', background: isDark ? 'rgba(34,211,238,0.07)' : 'rgba(34,211,238,0.05)', border: `1px solid ${alpha('#22d3ee', 0.2)}` }}>
              <Typography sx={{ fontSize: '0.68rem', color: isDark ? '#22d3ee' : '#0891b2', fontWeight: 500, lineHeight: 1.55 }}>
                We will poll this endpoint every 15 minutes. Expected: JSON object or array.
              </Typography>
            </Box>
            <Box component="button" sx={{ width: '100%', border: 'none', cursor: 'pointer', py: 1.1, borderRadius: '12px', background: 'linear-gradient(135deg, #22d3ee, #818cf8)', color: '#fff', fontSize: '0.82rem', fontWeight: 700, transition: 'all 0.18s ease', boxShadow: '0 4px 16px rgba(34,211,238,0.3)', '&:hover': { opacity: 0.9, transform: 'translateY(-1px)' } }}>
              Connect API
            </Box>
          </Box>
        )}
      </Box>
    </Modal>
  );
}


// ── Category badge shown at top of each form step ─────────────────────────────
function CategoryBadge({ cat, isDark, theme }: { cat: DataCategory; isDark: boolean; theme: Theme }) {
  const cfg = CATEGORY_CONFIG[cat];
  const Icon = CATEGORY_ICONS[cat];
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.75,
      px: 1.25, py: 0.6, borderRadius: '10px',
      background: isDark ? alpha(cfg.color, 0.14) : alpha(cfg.color, 0.09),
      border: `1px solid ${alpha(cfg.color, 0.3)}`,
      alignSelf: 'flex-start',
    }}>
      <Icon sx={{ fontSize: 14, color: cfg.color }} />
      <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, color: cfg.color, letterSpacing: '-0.01em' }}>
        {cfg.emoji} {cfg.label}
      </Typography>
    </Box>
  );
}

export default function MyDataPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients.primary : lightGradients.primary;

  const [activeCategory, setActiveCategory] = useState<DataCategory | 'all' | 'sources'>('all');
  const [search, setSearch] = useState('');
  const [selectedEntry, setSelectedEntry] = useState<DataEntry | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [toast, setToast] = useState<{ msg: string; severity: 'success' | 'error' } | null>(null);

  // ── Real API data ──────────────────────────────────────────────────────────
  const { data: statsData }   = useDataStats();
  const { data: entriesData, isLoading: entriesLoading } = useDataEntriesByCategory(
    activeCategory === 'sources' ? 'all' : activeCategory,
  );

  const apiEntries = entriesData?.entries ?? [];

  const filteredEntries = useMemo(() => {
    if (!search) return apiEntries;
    const q = search.toLowerCase();
    return apiEntries.filter(e =>
      e.title.toLowerCase().includes(q) ||
      Object.values(e.structured_data).some(v => String(v).toLowerCase().includes(q)),
    );
  }, [apiEntries, search]);

  // Group by category for "all" view
  const groupedEntries = useMemo(() => {
    const map = new Map<DataCategory, DataEntry[]>();
    filteredEntries.forEach(e => {
      const cat = e.category as DataCategory;
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(e);
    });
    return map;
  }, [filteredEntries]);

  const totalEntries = statsData?.total_entries ?? 0;
  const totalSources = statsData?.total_sources ?? 0;
  const avgQuality   = statsData?.avg_quality ?? 0;
  const aiReady      = statsData?.ai_ready_entries ?? 0;

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
            entries={apiEntries}
            activeCategory={activeCategory}
            onSelect={setActiveCategory}
            isDark={isDark}
            theme={theme}
            search={search}
            onSearch={setSearch}
            sourcesCount={totalSources}
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
            const lowCount     = apiEntries.filter(e => e.quality_score < 75).length;
            const missingCount = apiEntries.filter(e => (e.missing_fields?.length ?? 0) > 0).length;
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

      {/* Toast notifications */}
      <Snackbar
        open={!!toast}
        autoHideDuration={4000}
        onClose={() => setToast(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={toast?.severity ?? 'success'} onClose={() => setToast(null)} sx={{ fontSize: '0.78rem' }}>
          {toast?.msg}
        </Alert>
      </Snackbar>
    </Box>
  );
}
