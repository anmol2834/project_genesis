'use client';

import { useCallback, useMemo, useState } from 'react';
import { Box, Typography, useTheme, alpha } from '@mui/material';
import { ParentSize } from '@visx/responsive';
import { scaleBand, scaleLinear } from '@visx/scale';
import { Bar } from '@visx/shape';
import { Group } from '@visx/group';
import { GridRows } from '@visx/grid';
import { AxisBottom, AxisLeft } from '@visx/axis';
import { LinearGradient } from '@visx/gradient';
import { useTooltip, TooltipWithBounds, defaultStyles } from '@visx/tooltip';

// ── Data ─────────────────────────────────────────────────────────────────────
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

const RAW_DATA = [
  { month: 'Jan', sent: 18400, replies: 4200, ai: 3100 },
  { month: 'Feb', sent: 22100, replies: 5800, ai: 4400 },
  { month: 'Mar', sent: 31500, replies: 8900, ai: 7200 },
  { month: 'Apr', sent: 27800, replies: 7100, ai: 5900 },
  { month: 'May', sent: 35200, replies: 10400, ai: 8800 },
  { month: 'Jun', sent: 41000, replies: 13200, ai: 11500 },
  { month: 'Jul', sent: 38600, replies: 11800, ai: 10200 },
  { month: 'Aug', sent: 44900, replies: 15100, ai: 13400 },
  { month: 'Sep', sent: 52300, replies: 18600, ai: 16800 },
  { month: 'Oct', sent: 61800, replies: 22400, ai: 20100 },
  { month: 'Nov', sent: 74200, replies: 27900, ai: 25600 },
  { month: 'Dec', sent: 89500, replies: 34200, ai: 31800 },
];

type DataPoint = typeof RAW_DATA[0];
type SeriesKey = 'sent' | 'replies' | 'ai';

const SERIES: { key: SeriesKey; label: string; gradId: string; from: string; to: string }[] = [
  { key: 'sent',    label: 'Emails Sent',   gradId: 'grad-sent',    from: '#6366f1', to: '#818cf8' },
  { key: 'replies', label: 'Replies',        gradId: 'grad-replies', from: '#10b981', to: '#34d399' },
  { key: 'ai',      label: 'AI Responses',  gradId: 'grad-ai',      from: '#8b5cf6', to: '#c084fc' },
];

const fmt = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M`
  : n >= 1_000   ? `${(n / 1_000).toFixed(0)}K`
  : `${n}`;

// ── Tooltip type ──────────────────────────────────────────────────────────────
interface TooltipData { month: string; sent: number; replies: number; ai: number; x: number }

// ── Inner chart (receives measured width) ────────────────────────────────────
const MARGIN = { top: 20, right: 16, bottom: 44, left: 58 };
// Minimum width per month so bars never collapse on small screens
const MIN_MONTH_WIDTH = 42;

function ChartInner({ width, height, isDark }: { width: number; height: number; isDark: boolean }) {
  const theme = useTheme();
  const [active, setActive] = useState<SeriesKey | null>(null);

  const { showTooltip, hideTooltip, tooltipData, tooltipLeft, tooltipTop, tooltipOpen } =
    useTooltip<TooltipData>();

  // Ensure chart is wide enough so month labels never collapse
  const minInnerW = MONTHS.length * MIN_MONTH_WIDTH;
  const innerW = Math.max(width - MARGIN.left - MARGIN.right, minInnerW);
  const innerH = Math.max(height - MARGIN.top - MARGIN.bottom, 0);
  const totalW = innerW + MARGIN.left + MARGIN.right;

  const xScale = useMemo(() =>
    scaleBand<string>({
      domain: MONTHS,
      range: [0, innerW],
      padding: 0.28,
    }), [innerW]);

  const maxVal = useMemo(() => Math.max(...RAW_DATA.map(d => d.sent)), []);

  const yScale = useMemo(() =>
    scaleLinear<number>({
      domain: [0, maxVal * 1.12],
      range: [innerH, 0],
      nice: true,
    }), [innerH, maxVal]);

  const groupW = xScale.bandwidth();
  const barW   = Math.max((groupW - 4) / 3, 4);

  const axisColor   = isDark ? 'rgba(203,213,225,0.25)' : 'rgba(15,23,42,0.15)';
  const tickColor   = isDark ? 'rgba(203,213,225,0.5)'  : 'rgba(15,23,42,0.45)';
  const gridColor   = isDark ? 'rgba(203,213,225,0.07)' : 'rgba(15,23,42,0.06)';

  const handleMouseMove = useCallback((d: DataPoint, barX: number) => {
    showTooltip({
      tooltipData: { ...d, x: barX },
      tooltipLeft: MARGIN.left + barX + groupW / 2,
      tooltipTop:  MARGIN.top + yScale(d.sent) - 12,
    });
  }, [showTooltip, groupW, yScale]);

  return (
    <Box sx={{ position: 'relative', userSelect: 'none' }}>
      <svg width={totalW} height={height} style={{ overflow: 'visible' }}>
        <defs>
          {SERIES.map(s => (
            <LinearGradient key={s.gradId} id={s.gradId} from={s.from} to={s.to} vertical />
          ))}
          {/* Glow filter */}
          <filter id="bar-glow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        <Group left={MARGIN.left} top={MARGIN.top}>
          {/* Grid */}
          <GridRows
            scale={yScale}
            width={innerW}
            stroke={gridColor}
            strokeDasharray="4 3"
            numTicks={5}
          />

          {/* Bars */}
          {RAW_DATA.map((d) => {
            const x0 = xScale(d.month) ?? 0;
            return (
              <Group key={d.month}>
                {SERIES.map((s, si) => {
                  const barX  = x0 + si * (barW + 2);
                  const barH  = Math.max(innerH - yScale(d[s.key]), 0);
                  const barY  = innerH - barH;
                  const dim   = active !== null && active !== s.key;
                  return (
                    <g key={s.key}>
                      {/* Shadow bar */}
                      <rect
                        x={barX + 2} y={barY + 4}
                        width={barW} height={barH}
                        rx={4} fill={s.from}
                        opacity={dim ? 0 : 0.15}
                        style={{ transition: 'opacity 0.2s' }}
                      />
                      <Bar
                        x={barX} y={barY}
                        width={barW} height={barH}
                        rx={4}
                        fill={`url(#${s.gradId})`}
                        opacity={dim ? 0.2 : 1}
                        style={{ transition: 'opacity 0.2s', cursor: 'pointer' }}
                        onMouseEnter={() => { setActive(s.key); handleMouseMove(d, x0); }}
                        onMouseLeave={() => { setActive(null); hideTooltip(); }}
                      />
                    </g>
                  );
                })}
                {/* Invisible hover zone */}
                <rect
                  x={x0} y={0} width={groupW} height={innerH}
                  fill="transparent"
                  onMouseEnter={() => handleMouseMove(d, x0)}
                  onMouseLeave={() => { setActive(null); hideTooltip(); }}
                />
              </Group>
            );
          })}

          {/* X axis */}
          <AxisBottom
            top={innerH}
            scale={xScale}
            stroke={axisColor}
            tickStroke="transparent"
            tickLabelProps={() => ({
              fill: tickColor,
              fontSize: 11,
              fontFamily: 'Inter, sans-serif',
              fontWeight: 500,
              textAnchor: 'middle',
              dy: '0.5em',
            })}
          />

          {/* Y axis */}
          <AxisLeft
            scale={yScale}
            stroke={axisColor}
            tickStroke="transparent"
            numTicks={5}
            tickFormat={(v) => fmt(Number(v))}
            tickLabelProps={() => ({
              fill: tickColor,
              fontSize: 11,
              fontFamily: 'Inter, sans-serif',
              fontWeight: 500,
              textAnchor: 'end',
              dx: '-0.4em',
              dy: '0.3em',
            })}
          />
        </Group>
      </svg>

      {/* Tooltip */}
      {tooltipOpen && tooltipData && (
        <TooltipWithBounds
          left={tooltipLeft}
          top={tooltipTop}
          style={{
            ...defaultStyles,
            background: isDark ? '#1e293b' : '#fff',
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(15,23,42,0.1)'}`,
            borderRadius: 10,
            padding: '10px 14px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
            minWidth: 140,
          }}
        >
          <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: 'text.primary', mb: 0.75 }}>
            {tooltipData.month} 2025
          </Typography>
          {SERIES.map(s => (
            <Box key={s.key} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.4 }}>
              <Box sx={{ width: 8, height: 8, borderRadius: '50%', background: s.from, flexShrink: 0 }} />
              <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', flex: 1 }}>{s.label}</Typography>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: 'text.primary' }}>
                {fmt(tooltipData[s.key])}
              </Typography>
            </Box>
          ))}
        </TooltipWithBounds>
      )}
    </Box>
  );
}

// ── Legend ────────────────────────────────────────────────────────────────────
function Legend({ active, onHover }: { active: SeriesKey | null; onHover: (k: SeriesKey | null) => void }) {
  return (
    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
      {SERIES.map(s => (
        <Box
          key={s.key}
          onMouseEnter={() => onHover(s.key)}
          onMouseLeave={() => onHover(null)}
          sx={{
            display: 'flex', alignItems: 'center', gap: 0.6,
            cursor: 'default',
            opacity: active !== null && active !== s.key ? 0.35 : 1,
            transition: 'opacity 0.2s',
          }}
        >
          <Box sx={{
            width: 10, height: 10, borderRadius: '3px',
            background: `linear-gradient(135deg, ${s.from}, ${s.to})`,
          }} />
          <Typography sx={{ fontSize: '0.7rem', fontWeight: 500, color: 'text.secondary' }}>
            {s.label}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}

// ── Public export ─────────────────────────────────────────────────────────────
export default function EmailChart() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [active, setActive] = useState<SeriesKey | null>(null);

  return (
    <Box sx={{
      borderRadius: '14px',
      border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
      background: isDark ? 'rgba(15,23,42,0.7)' : theme.palette.background.paper,
      backdropFilter: isDark ? 'blur(12px)' : 'none',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <Box sx={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexWrap: 'wrap', gap: 1,
        px: 2.5, pt: 2, pb: 1.5,
        borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : theme.palette.divider}`,
      }}>
        <Box>
          <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, color: 'text.primary', letterSpacing: '-0.01em' }}>
            Email Performance
          </Typography>
          <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', mt: 0.2 }}>
            Jan – Dec 2025 · monthly overview
          </Typography>
        </Box>
        <Legend active={active} onHover={setActive} />
      </Box>

      {/* Chart — horizontally scrollable on small screens */}
      <Box
        sx={{
          overflowX: 'auto',
          overflowY: 'hidden',
          px: 1,
          pt: 1,
          pb: 0.5,
          height: { xs: 220, sm: 260 },
          '&::-webkit-scrollbar': { height: 3 },
          '&::-webkit-scrollbar-track': { background: 'transparent' },
          '&::-webkit-scrollbar-thumb': {
            background: isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.1)',
            borderRadius: 2,
          },
        }}
      >
        {/* ParentSize measures the scroll container; chart may be wider than container */}
        <ParentSize>
          {({ width, height }) =>
            width > 0 && height > 0
              ? <ChartInner width={width} height={height} isDark={isDark} />
              : null
          }
        </ParentSize>
      </Box>
    </Box>
  );
}
