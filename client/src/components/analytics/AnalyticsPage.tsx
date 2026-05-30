'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { Box, Typography, useTheme, alpha, IconButton, Button, Tooltip, type Theme } from '@mui/material';
import { ParentSize } from '@visx/responsive';
import { scaleLinear, scalePoint } from '@visx/scale';
import { LinePath, Area } from '@visx/shape';
import { curveMonotoneX } from 'd3-shape';
import { GridRows } from '@visx/grid';
import { AxisBottom, AxisLeft } from '@visx/axis';
import { LinearGradient } from '@visx/gradient';
import { Group } from '@visx/group';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import TrendingDownRoundedIcon from '@mui/icons-material/TrendingDownRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import ReplyRoundedIcon from '@mui/icons-material/ReplyRounded';
import DraftsRoundedIcon from '@mui/icons-material/DraftsRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import InfoRoundedIcon from '@mui/icons-material/InfoRounded';
import AccessTimeRoundedIcon from '@mui/icons-material/AccessTimeRounded';
import SpeedRoundedIcon from '@mui/icons-material/SpeedRounded';
import { lightGradients, darkGradients } from '@/theme/palette';
import {
  SERIES, KPI, CAMPAIGN_STATS, ACCOUNT_STATS, AI_INSIGHTS,
  LEAD_ENGAGEMENT, AI_TONE_PERF, TimeRange, DayPoint,
} from './analyticsData';

// ── Animated counter ──────────────────────────────────────────────────────────
function CountUp({ target, decimals = 0, suffix = '' }: { target: number; decimals?: number; suffix?: string }) {
  const [val, setVal] = useState(0);
  const frame = useRef<number | null>(null);
  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / 1100, 1);
      const v = (1 - Math.pow(1 - p, 3)) * target;
      setVal(parseFloat(v.toFixed(decimals)));
      if (p < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => { if (frame.current) cancelAnimationFrame(frame.current); };
  }, [target, decimals]);
  return <>{decimals > 0 ? val.toFixed(decimals) : val.toLocaleString()}{suffix}</>;
}

// ── Sparkline (tiny inline chart) ────────────────────────────────────────────
function Sparkline({ data, color, width = 80, height = 28 }: {
  data: number[]; color: string; width?: number; height?: number;
}) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => ({
    x: (i / (data.length - 1)) * width,
    y: height - ((v - min) / range) * (height - 4) - 2,
  }));
  const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const area = `${d} L${width},${height} L0,${height} Z`;
  return (
    <svg width={width} height={height} style={{ overflow: 'visible', flexShrink: 0 }}>
      <defs>
        <linearGradient id={`sg-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.25} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#sg-${color.replace('#', '')})`} />
      <path d={d} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pts[pts.length - 1].x} cy={pts[pts.length - 1].y} r={2.5} fill={color} />
    </svg>
  );
}

// ── Full line chart ───────────────────────────────────────────────────────────
function LineChart({ series, colors, labels, isDark, height = 180 }: {
  series: DayPoint[][];
  colors: string[];
  labels: string[];
  isDark: boolean;
  height?: number;
}) {
  const [hovered, setHovered] = useState<{ x: number; y: number; idx: number } | null>(null);

  return (
    <ParentSize>
      {({ width }) => {
        if (width < 10) return null;
        const margin = { top: 12, right: 12, bottom: 28, left: 36 };
        const innerW = width - margin.left - margin.right;
        const innerH = height - margin.top - margin.bottom;

        const allVals = series.flat().map(d => d.value);
        const maxVal = Math.max(...allVals) * 1.15;

        const xScale = scalePoint({
          domain: series[0].map(d => d.date),
          range: [0, innerW],
          padding: 0.1,
        });
        const yScale = scaleLinear({ domain: [0, maxVal], range: [innerH, 0] });

        const tickCount = series[0].length <= 7 ? series[0].length : Math.min(8, series[0].length);
        const step = Math.floor(series[0].length / tickCount);
        const tickValues = series[0].filter((_, i) => i % step === 0).map(d => d.date);

        return (
          <svg width={width} height={height} style={{ overflow: 'visible' }}>
            <defs>
              {colors.map((c, i) => (
                <linearGradient key={i} id={`lc-${i}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={c} stopOpacity={isDark ? 0.18 : 0.12} />
                  <stop offset="100%" stopColor={c} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <Group left={margin.left} top={margin.top}>
              <GridRows
                scale={yScale} width={innerW} numTicks={4}
                stroke={isDark ? 'rgba(255,255,255,0.05)' : 'rgba(15,23,42,0.06)'}
                strokeDasharray="3,3"
              />
              {series.map((s, si) => (
                <Area
                  key={si}
                  data={s}
                  x={d => xScale(d.date) ?? 0}
                  y={d => yScale(d.value)}
                  y0={() => innerH}
                  curve={curveMonotoneX}
                  fill={`url(#lc-${si})`}
                />
              ))}
              {series.map((s, si) => (
                <LinePath
                  key={si}
                  data={s}
                  x={d => xScale(d.date) ?? 0}
                  y={d => yScale(d.value)}
                  curve={curveMonotoneX}
                  stroke={colors[si]}
                  strokeWidth={2}
                  strokeLinecap="round"
                />
              ))}
              <AxisBottom
                scale={xScale} top={innerH}
                tickValues={tickValues}
                tickFormat={v => String(v)}
                stroke="transparent"
                tickStroke="transparent"
                tickLabelProps={() => ({
                  fill: isDark ? 'rgba(255,255,255,0.3)' : 'rgba(15,23,42,0.35)',
                  fontSize: 9, textAnchor: 'middle', fontFamily: 'Inter, sans-serif',
                })}
              />
              <AxisLeft
                scale={yScale} numTicks={4}
                stroke="transparent" tickStroke="transparent"
                tickFormat={v => Number(v) >= 1000 ? `${(Number(v) / 1000).toFixed(0)}k` : String(v)}
                tickLabelProps={() => ({
                  fill: isDark ? 'rgba(255,255,255,0.3)' : 'rgba(15,23,42,0.35)',
                  fontSize: 9, textAnchor: 'end', fontFamily: 'Inter, sans-serif', dx: -4,
                })}
              />
            </Group>
          </svg>
        );
      }}
    </ParentSize>
  );
}

// ── Horizontal bar chart ──────────────────────────────────────────────────────
function HBarChart({ data, isDark, height = 140 }: {
  data: { label: string; value: number; color: string }[];
  isDark: boolean; height?: number;
}) {
  const max = Math.max(...data.map(d => d.value));
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.9, py: 0.5 }}>
      {data.map((d, i) => (
        <Box key={d.label} sx={{
          display: 'flex', alignItems: 'center', gap: 1,
          animation: `barIn 0.4s ease-out ${i * 0.07}s both`,
          '@keyframes barIn': { from: { opacity: 0, transform: 'translateX(-8px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
        }}>
          <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', minWidth: 80, textAlign: 'right' }}>
            {d.label}
          </Typography>
          <Box sx={{ flex: 1, height: 6, borderRadius: 3, background: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(15,23,42,0.07)', overflow: 'hidden' }}>
            <Box sx={{
              height: '100%', borderRadius: 3,
              width: `${(d.value / max) * 100}%`,
              background: d.color,
              transition: 'width 0.9s cubic-bezier(0.4,0,0.2,1)',
              boxShadow: `0 0 8px ${alpha(d.color, 0.4)}`,
            }} />
          </Box>
          <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: d.color, minWidth: 36 }}>
            {d.value}%
          </Typography>
        </Box>
      ))}
    </Box>
  );
}

// ── Donut chart (SVG) ─────────────────────────────────────────────────────────
function DonutChart({ data, size = 100 }: {
  data: { label: string; value: number; color: string }[];
  size?: number;
}) {
  const total = data.reduce((s, d) => s + d.value, 0);
  const r = size / 2 - 8;
  const cx = size / 2;
  const cy = size / 2;
  const strokeW = 10;
  const circumference = 2 * Math.PI * r;

  let offset = 0;
  const segments = data.map(d => {
    const pct = d.value / total;
    const dash = pct * circumference;
    const gap = circumference - dash;
    const seg = { ...d, dash, gap, offset };
    offset += dash;
    return seg;
  });

  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)', flexShrink: 0 }}>
      {segments.map((seg, i) => (
        <circle
          key={i}
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke={seg.color}
          strokeWidth={strokeW}
          strokeDasharray={`${seg.dash} ${seg.gap}`}
          strokeDashoffset={-seg.offset}
          strokeLinecap="butt"
          style={{ transition: 'stroke-dasharray 0.9s ease' }}
        />
      ))}
    </svg>
  );
}

// ── KPI metric strip ──────────────────────────────────────────────────────────
function MetricStrip({ range, isDark, theme }: { range: TimeRange; isDark: boolean; theme: Theme }) {
  const kpi = KPI[range];
  const series = SERIES[range];

  const metrics = [
    {
      label: 'Emails Sent', value: kpi.emailsSent, decimals: 0, suffix: '',
      delta: kpi.deltaEmails, color: '#818cf8',
      spark: series.emailsSent.map(d => d.value),
      Icon: EmailRoundedIcon,
    },
    {
      label: 'Open Rate', value: kpi.openRate, decimals: 1, suffix: '%',
      delta: kpi.deltaOpen, color: '#22d3ee',
      spark: series.opens.map(d => d.value),
      Icon: DraftsRoundedIcon,
    },
    {
      label: 'Reply Rate', value: kpi.replyRate, decimals: 1, suffix: '%',
      delta: kpi.deltaReply, color: '#34d399',
      spark: series.replies.map(d => d.value),
      Icon: ReplyRoundedIcon,
    },
    {
      label: 'Conv. Rate', value: kpi.convRate, decimals: 1, suffix: '%',
      delta: kpi.deltaConv, color: '#fbbf24',
      spark: series.replies.map(d => Math.round(d.value * 0.21)),
      Icon: BoltRoundedIcon,
    },
    {
      label: 'AI Success', value: kpi.aiSuccessRate, decimals: 0, suffix: '%',
      delta: 4.2, color: '#c084fc',
      spark: series.aiReplies.map(d => d.value),
      Icon: AutoAwesomeRoundedIcon,
    },
    {
      label: 'Avg Response', value: 4.2, decimals: 1, suffix: 'h',
      delta: -0.8, color: '#f472b6',
      spark: [5.1, 4.8, 4.6, 4.9, 4.3, 4.1, 4.2],
      Icon: AccessTimeRoundedIcon,
    },
  ];

  return (
    <Box sx={{
      display: 'grid',
      gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(3, 1fr)', lg: 'repeat(6, 1fr)' },
      borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
    }}>
      {metrics.map((m, i) => (
        <Box key={m.label} sx={{
          px: { xs: 1.5, sm: 2 }, py: 1.75,
          borderRight: i < metrics.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : theme.palette.divider}` : 'none',
          borderBottom: { xs: i < 4 ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : theme.palette.divider}` : 'none', sm: i < 3 ? `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : theme.palette.divider}` : 'none', lg: 'none' },
          position: 'relative', overflow: 'hidden',
          transition: 'background 0.15s ease',
          '&:hover': { background: isDark ? alpha(m.color, 0.04) : alpha(m.color, 0.025) },
          '&::before': {
            content: '""', position: 'absolute', top: 0, left: 0, right: 0, height: '2px',
            background: `linear-gradient(90deg, ${m.color}, ${alpha(m.color, 0)})`,
          },
          animation: `metricIn 0.35s ease-out ${i * 0.06}s both`,
          '@keyframes metricIn': { from: { opacity: 0, transform: 'translateY(6px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 0.75 }}>
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.3 }}>
                <m.Icon sx={{ fontSize: 11, color: m.color }} />
                <Typography sx={{ fontSize: '0.6rem', fontWeight: 600, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                  {m.label}
                </Typography>
              </Box>
              <Typography sx={{ fontSize: { xs: '1.3rem', sm: '1.5rem' }, fontWeight: 800, letterSpacing: '-0.04em', lineHeight: 1, color: 'text.primary' }}>
                <CountUp target={m.value} decimals={m.decimals} suffix={m.suffix} />
              </Typography>
            </Box>
            <Sparkline data={m.spark} color={m.color} width={60} height={26} />
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
            {m.delta >= 0
              ? <TrendingUpRoundedIcon sx={{ fontSize: 11, color: '#34d399' }} />
              : <TrendingDownRoundedIcon sx={{ fontSize: 11, color: '#f87171' }} />}
            <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: m.delta >= 0 ? '#34d399' : '#f87171' }}>
              {m.delta >= 0 ? '+' : ''}{m.delta}{m.suffix || '%'}
            </Typography>
            <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>vs prev period</Typography>
          </Box>
        </Box>
      ))}
    </Box>
  );
}

// ── AI insights strip ─────────────────────────────────────────────────────────
function InsightsStrip({ isDark, theme }: { isDark: boolean; theme: Theme }) {
  const [idx, setIdx] = useState(0);
  const insight = AI_INSIGHTS[idx];

  const typeMap = {
    positive: { color: '#34d399', Icon: CheckCircleRoundedIcon, bg: isDark ? 'rgba(52,211,153,0.08)' : 'rgba(52,211,153,0.06)' },
    warning:  { color: '#fbbf24', Icon: WarningAmberRoundedIcon, bg: isDark ? 'rgba(251,191,36,0.08)' : 'rgba(251,191,36,0.06)' },
    neutral:  { color: '#818cf8', Icon: InfoRoundedIcon, bg: isDark ? 'rgba(129,140,248,0.08)' : 'rgba(129,140,248,0.06)' },
  };

  return (
    <Box sx={{
      px: { xs: 2, sm: 3 }, py: 1,
      borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
      display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap',
      background: isDark ? 'rgba(255,255,255,0.01)' : alpha(theme.palette.text.primary, 0.005),
    }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
        <AutoAwesomeRoundedIcon sx={{ fontSize: 12, color: '#c084fc' }} />
        <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: '#c084fc', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          AI Insights
        </Typography>
      </Box>
      <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', gap: 1, overflow: 'hidden' }}>
        {AI_INSIGHTS.map((ins, i) => {
          const cfg = typeMap[ins.type];
          const active = i === idx;
          return (
            <Box key={ins.id} component="button" onClick={() => setIdx(i)} sx={{
              display: 'flex', alignItems: 'center', gap: 0.5,
              px: 0.9, py: 0.4, borderRadius: '7px', cursor: 'pointer',
              background: active ? cfg.bg : 'transparent',
              border: `1px solid ${active ? alpha(cfg.color, 0.3) : 'transparent'}`,
              transition: 'all 0.15s ease', flexShrink: 0,
              '&:hover': { background: cfg.bg },
            }}>
              <cfg.Icon sx={{ fontSize: 10, color: cfg.color }} />
              <Typography sx={{ fontSize: '0.62rem', fontWeight: active ? 700 : 500, color: active ? cfg.color : 'text.disabled', whiteSpace: 'nowrap' }}>
                {ins.title}
              </Typography>
              {ins.delta && active && (
                <Box sx={{ px: 0.45, py: 0.1, borderRadius: '4px', background: alpha(cfg.color, 0.15) }}>
                  <Typography sx={{ fontSize: '0.52rem', fontWeight: 800, color: cfg.color }}>{ins.delta}</Typography>
                </Box>
              )}
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}

// ── Chart section wrapper ─────────────────────────────────────────────────────
function Section({ title, subtitle, color = '#818cf8', children, isDark, theme, action }: {
  title: string; subtitle?: string; color?: string;
  children: React.ReactNode; isDark: boolean; theme: Theme;
  action?: React.ReactNode;
}) {
  return (
    <Box sx={{
      borderRadius: '14px', overflow: 'hidden',
      border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
      background: isDark ? 'rgba(255,255,255,0.02)' : theme.palette.background.paper,
    }}>
      <Box sx={{
        px: 2, py: 1.25,
        borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: isDark ? alpha(color, 0.04) : alpha(color, 0.025),
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Box sx={{ width: 3, height: 16, borderRadius: 2, background: color, flexShrink: 0 }} />
          <Box>
            <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: 'text.primary', lineHeight: 1.2 }}>{title}</Typography>
            {subtitle && <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', mt: 0.1 }}>{subtitle}</Typography>}
          </Box>
        </Box>
        {action}
      </Box>
      <Box sx={{ p: 2 }}>{children}</Box>
    </Box>
  );
}

// ── Chart legend ──────────────────────────────────────────────────────────────
function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', mb: 1 }}>
      {items.map(item => (
        <Box key={item.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
          <Box sx={{ width: 20, height: 2.5, borderRadius: 2, background: item.color }} />
          <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>{item.label}</Typography>
        </Box>
      ))}
    </Box>
  );
}

// ── Campaign performance table ────────────────────────────────────────────────
function CampaignTable({ isDark, theme }: { isDark: boolean; theme: Theme }) {
  return (
    <Section title="Campaign Performance" subtitle="Breakdown by campaign" color="#818cf8" isDark={isDark} theme={theme}>
      {/* Header */}
      <Box sx={{
        display: 'grid', gridTemplateColumns: '1fr 70px 70px 70px 70px 80px',
        alignItems: 'center', gap: 1, px: 0.5, pb: 0.75, mb: 0.5,
        borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.05)' : theme.palette.divider}`,
      }}>
        {['Campaign', 'Sent', 'Open%', 'Reply%', 'Conv%', 'Trend'].map(h => (
          <Typography key={h} sx={{ fontSize: '0.58rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
            {h}
          </Typography>
        ))}
      </Box>
      {CAMPAIGN_STATS.map((c, i) => (
        <Box key={c.id} sx={{
          display: 'grid', gridTemplateColumns: '1fr 70px 70px 70px 70px 80px',
          alignItems: 'center', gap: 1, px: 0.5, py: 0.85,
          borderBottom: i < CAMPAIGN_STATS.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : theme.palette.divider}` : 'none',
          transition: 'background 0.12s ease',
          '&:hover': { background: isDark ? 'rgba(255,255,255,0.025)' : alpha(theme.palette.text.primary, 0.02), borderRadius: '8px' },
          animation: `rowIn 0.22s ease-out ${i * 0.05}s both`,
          '@keyframes rowIn': { from: { opacity: 0, transform: 'translateX(-4px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
            <Box sx={{ width: 3, height: 28, borderRadius: 2, background: c.color, flexShrink: 0 }} />
            <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {c.name}
            </Typography>
          </Box>
          <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: 'text.secondary' }}>{c.sent.toLocaleString()}</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
            <Box sx={{ width: 24, height: 3, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)', overflow: 'hidden' }}>
              <Box sx={{ height: '100%', borderRadius: 2, width: `${c.openRate}%`, background: '#22d3ee' }} />
            </Box>
            <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#22d3ee' }}>{c.openRate}%</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
            <Box sx={{ width: 24, height: 3, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)', overflow: 'hidden' }}>
              <Box sx={{ height: '100%', borderRadius: 2, width: `${c.replyRate * 4}%`, background: '#34d399' }} />
            </Box>
            <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#34d399' }}>{c.replyRate}%</Typography>
          </Box>
          <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#fbbf24' }}>{c.convRate}%</Typography>
          <Sparkline data={c.trend} color={c.color} width={72} height={22} />
        </Box>
      ))}
    </Section>
  );
}

// ── Account performance ───────────────────────────────────────────────────────
function AccountPerf({ isDark, theme }: { isDark: boolean; theme: Theme }) {
  return (
    <Section title="Account Performance" subtitle="Per inbox breakdown" color="#22d3ee" isDark={isDark} theme={theme}>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {ACCOUNT_STATS.map((acc, i) => (
          <Box key={acc.id} sx={{
            display: 'grid', gridTemplateColumns: '1fr 60px 60px 80px',
            alignItems: 'center', gap: 1, py: 0.9,
            borderBottom: i < ACCOUNT_STATS.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : theme.palette.divider}` : 'none',
            animation: `rowIn 0.22s ease-out ${i * 0.06}s both`,
            '@keyframes rowIn': { from: { opacity: 0, transform: 'translateX(-4px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
              <Box sx={{
                width: 28, height: 28, borderRadius: '8px', flexShrink: 0,
                background: alpha(acc.color, isDark ? 0.18 : 0.12),
                border: `1px solid ${alpha(acc.color, 0.25)}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <EmailRoundedIcon sx={{ fontSize: 13, color: acc.color }} />
              </Box>
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {acc.name}
                </Typography>
                <Typography sx={{ fontSize: '0.58rem', color: 'text.disabled', textTransform: 'capitalize' }}>{acc.provider}</Typography>
              </Box>
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: 'text.primary' }}>{acc.sent.toLocaleString()}</Typography>
              <Typography sx={{ fontSize: '0.55rem', color: 'text.disabled' }}>sent</Typography>
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: '#34d399' }}>{acc.replyRate}%</Typography>
              <Typography sx={{ fontSize: '0.55rem', color: 'text.disabled' }}>reply</Typography>
            </Box>
            {/* Health bar */}
            <Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.3 }}>
                <Typography sx={{ fontSize: '0.55rem', color: 'text.disabled' }}>Health</Typography>
                <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: acc.health >= 85 ? '#34d399' : acc.health >= 70 ? '#fbbf24' : '#f87171' }}>
                  {acc.health}%
                </Typography>
              </Box>
              <Box sx={{ height: 3, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.07)', overflow: 'hidden' }}>
                <Box sx={{
                  height: '100%', borderRadius: 2, width: `${acc.health}%`,
                  background: acc.health >= 85 ? '#34d399' : acc.health >= 70 ? '#fbbf24' : '#f87171',
                  transition: 'width 0.9s ease',
                }} />
              </Box>
            </Box>
          </Box>
        ))}
      </Box>
    </Section>
  );
}

// ── AI performance section ────────────────────────────────────────────────────
function AIPerformance({ range, isDark, theme }: { range: TimeRange; isDark: boolean; theme: Theme }) {
  const kpi = KPI[range];
  const series = SERIES[range];

  return (
    <Section title="AI Performance" subtitle="AI vs manual reply analysis" color="#c084fc" isDark={isDark} theme={theme}>
      {/* Top stats row */}
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1, mb: 2 }}>
        {[
          { label: 'AI Success Rate', value: kpi.aiSuccessRate, suffix: '%', color: '#c084fc' },
          { label: 'AI vs Manual',    value: kpi.aiVsManual,    suffix: '%', color: '#818cf8' },
          { label: 'Avg Response',    value: 4.2,               suffix: 'h', color: '#22d3ee' },
        ].map(s => (
          <Box key={s.label} sx={{
            px: 1.25, py: 1, borderRadius: '10px',
            background: isDark ? alpha(s.color, 0.08) : alpha(s.color, 0.05),
            border: `1px solid ${alpha(s.color, isDark ? 0.2 : 0.15)}`,
            textAlign: 'center',
          }}>
            <Typography sx={{ fontSize: '1.2rem', fontWeight: 800, letterSpacing: '-0.04em', color: s.color, lineHeight: 1 }}>
              <CountUp target={s.value} decimals={s.suffix === 'h' ? 1 : 0} suffix={s.suffix} />
            </Typography>
            <Typography sx={{ fontSize: '0.58rem', color: 'text.disabled', mt: 0.3 }}>{s.label}</Typography>
          </Box>
        ))}
      </Box>

      {/* AI vs Manual chart */}
      <Box sx={{ mb: 1.5 }}>
        <Legend items={[{ label: 'AI Replies', color: '#c084fc' }, { label: 'Manual Replies', color: '#60a5fa' }]} />
        <Box sx={{ height: 120 }}>
          <LineChart
            series={[series.aiReplies, series.manualReplies]}
            colors={['#c084fc', '#60a5fa']}
            labels={['AI', 'Manual']}
            isDark={isDark}
            height={120}
          />
        </Box>
      </Box>

      {/* Tone performance */}
      <Box sx={{ pt: 1.25, borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}` }}>
        <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em', mb: 1 }}>
          Best Performing Tones
        </Typography>
        <HBarChart
          data={AI_TONE_PERF.map(t => ({ label: t.tone, value: t.replyRate, color: t.color }))}
          isDark={isDark}
        />
      </Box>
    </Section>
  );
}

// ── Lead engagement section ───────────────────────────────────────────────────
function LeadEngagement({ isDark, theme }: { isDark: boolean; theme: Theme }) {
  const total = LEAD_ENGAGEMENT.reduce((s, d) => s + d.value, 0);

  return (
    <Section title="Lead Engagement" subtitle="Response distribution" color="#34d399" isDark={isDark} theme={theme}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
        {/* Donut */}
        <Box sx={{ position: 'relative', flexShrink: 0 }}>
          <DonutChart data={LEAD_ENGAGEMENT} size={96} />
          <Box sx={{
            position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
          }}>
            <Typography sx={{ fontSize: '1rem', fontWeight: 800, color: 'text.primary', lineHeight: 1, letterSpacing: '-0.04em' }}>
              {LEAD_ENGAGEMENT[0].value}%
            </Typography>
            <Typography sx={{ fontSize: '0.5rem', color: 'text.disabled', mt: 0.2 }}>replied</Typography>
          </Box>
        </Box>

        {/* Legend + bars */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 0.85 }}>
          {LEAD_ENGAGEMENT.map((seg, i) => (
            <Box key={seg.label} sx={{
              animation: `barIn 0.35s ease-out ${i * 0.08}s both`,
              '@keyframes barIn': { from: { opacity: 0, transform: 'translateX(-6px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
            }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: seg.color, flexShrink: 0 }} />
                  <Typography sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>{seg.label}</Typography>
                </Box>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: seg.color }}>{seg.value}%</Typography>
              </Box>
              <Box sx={{ height: 4, borderRadius: 2, background: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(15,23,42,0.07)', overflow: 'hidden' }}>
                <Box sx={{
                  height: '100%', borderRadius: 2, width: `${seg.value}%`,
                  background: seg.color, transition: 'width 0.9s ease',
                  boxShadow: `0 0 6px ${alpha(seg.color, 0.4)}`,
                }} />
              </Box>
            </Box>
          ))}
        </Box>
      </Box>
    </Section>
  );
}

// ── Real-time activity feed ───────────────────────────────────────────────────
function RealtimeFeed({ isDark, theme }: { isDark: boolean; theme: Theme }) {
  const events = [
    { type: 'email', text: 'Email sent to sarah@techcorp.com', time: 'Just now', color: '#818cf8' },
    { type: 'reply', text: 'Reply received from mike@ventures.io', time: '2m ago', color: '#34d399' },
    { type: 'ai',    text: 'AI drafted reply for lisa@lv.capital', time: '4m ago', color: '#c084fc' },
    { type: 'open',  text: 'Email opened by david@enterprise.com', time: '7m ago', color: '#22d3ee' },
    { type: 'email', text: 'Sequence started: Cold Outbound', time: '12m ago', color: '#818cf8' },
    { type: 'reply', text: 'Reply received from emma@scale.io', time: '18m ago', color: '#34d399' },
    { type: 'ai',    text: 'AI reply sent to ryan@b2b.co', time: '24m ago', color: '#c084fc' },
  ];

  return (
    <Section title="Live Activity" subtitle="Real-time event stream" color="#34d399" isDark={isDark} theme={theme}
      action={
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, px: 0.75, py: 0.25, borderRadius: '6px', background: isDark ? 'rgba(52,211,153,0.12)' : 'rgba(52,211,153,0.08)', border: `1px solid ${alpha('#34d399', 0.25)}` }}>
          <Box sx={{ width: 5, height: 5, borderRadius: '50%', background: '#34d399', animation: 'pulse 2s ease-in-out infinite', '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.3 } } }} />
          <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: '#34d399' }}>Live</Typography>
        </Box>
      }
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {events.map((ev, i) => (
          <Box key={i} sx={{
            display: 'flex', alignItems: 'center', gap: 1,
            py: 0.75,
            borderBottom: i < events.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : theme.palette.divider}` : 'none',
            animation: `rowIn 0.2s ease-out ${i * 0.04}s both`,
            '@keyframes rowIn': { from: { opacity: 0, transform: 'translateX(-4px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
          }}>
            <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: ev.color, flexShrink: 0, boxShadow: i === 0 ? `0 0 6px ${ev.color}` : 'none' }} />
            <Typography sx={{ fontSize: '0.7rem', color: i === 0 ? 'text.primary' : 'text.secondary', flex: 1, fontWeight: i === 0 ? 600 : 400 }}>
              {ev.text}
            </Typography>
            <Typography sx={{ fontSize: '0.58rem', color: 'text.disabled', flexShrink: 0 }}>{ev.time}</Typography>
          </Box>
        ))}
      </Box>
    </Section>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [range, setRange] = useState<TimeRange>('7d');
  const series = SERIES[range];

  const rangeOpts: { id: TimeRange; label: string }[] = [
    { id: '7d', label: '7 days' },
    { id: '30d', label: '30 days' },
    { id: '90d', label: '90 days' },
  ];

  return (
    <Box sx={{ flex: 1, overflowY: 'auto', minHeight: 0,
      '&::-webkit-scrollbar': { width: 4 },
      '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
    }}>
      <Box sx={{ maxWidth: 1400, mx: 'auto', display: 'flex', flexDirection: 'column', pb: 4 }}>

        {/* ── Top header ── */}
        <Box sx={{
          px: { xs: 2, sm: 3 }, py: 1.5,
          borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap',
          animation: 'fadeDown 0.3s ease-out',
          '@keyframes fadeDown': { from: { opacity: 0, transform: 'translateY(-6px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        }}>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Typography sx={{ fontSize: { xs: '1.1rem', sm: '1.25rem' }, fontWeight: 800, letterSpacing: '-0.025em', color: 'text.primary', lineHeight: 1 }}>
                Analytics
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
              Insights across your automation system
            </Typography>
          </Box>

          {/* Time range selector */}
          <Box sx={{
            display: 'flex', gap: 0.25, p: 0.3, borderRadius: '10px',
            background: isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.04),
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
          }}>
            {rangeOpts.map(opt => (
              <Box key={opt.id} component="button" onClick={() => setRange(opt.id)} sx={{
                px: 1.25, py: 0.5, borderRadius: '8px', border: 'none', cursor: 'pointer',
                background: range === opt.id ? isDark ? 'rgba(129,140,248,0.2)' : alpha('#818cf8', 0.12) : 'transparent',
                color: range === opt.id ? (isDark ? '#818cf8' : theme.palette.primary.main) : theme.palette.text.secondary,
                fontSize: '0.72rem', fontWeight: range === opt.id ? 700 : 500,
                transition: 'all 0.15s ease',
              }}>
                {opt.label}
              </Box>
            ))}
          </Box>
        </Box>

        {/* ── KPI metric strip ── */}
        <MetricStrip range={range} isDark={isDark} theme={theme} />

        {/* ── AI insights strip ── */}
        <InsightsStrip isDark={isDark} theme={theme} />

        {/* ── Content ── */}
        <Box sx={{ px: { xs: 2, sm: 3 }, pt: 2.5, display: 'flex', flexDirection: 'column', gap: 2.5 }}>

          {/* ── Main trend chart — full width ── */}
          <Section
            title="Email Performance Trends"
            subtitle={`Sending & engagement over the last ${range === '7d' ? '7 days' : range === '30d' ? '30 days' : '90 days'}`}
            color="#818cf8" isDark={isDark} theme={theme}
            action={
              <Legend items={[
                { label: 'Emails Sent', color: '#818cf8' },
                { label: 'Opens', color: '#22d3ee' },
                { label: 'Replies', color: '#34d399' },
              ]} />
            }
          >
            <Box sx={{ height: 200 }}>
              <LineChart
                series={[series.emailsSent, series.opens, series.replies]}
                colors={['#818cf8', '#22d3ee', '#34d399']}
                labels={['Sent', 'Opens', 'Replies']}
                isDark={isDark}
                height={200}
              />
            </Box>
          </Section>

          {/* ── Two-column: Campaign table + right column ── */}
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', xl: '1.6fr 1fr' }, gap: 2.5 }}>
            <CampaignTable isDark={isDark} theme={theme} />

            {/* Right column stacked */}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
              <LeadEngagement isDark={isDark} theme={theme} />
              <AccountPerf isDark={isDark} theme={theme} />
            </Box>
          </Box>

          {/* ── Two-column: AI performance + Live feed ── */}
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1.4fr 1fr' }, gap: 2.5 }}>
            <AIPerformance range={range} isDark={isDark} theme={theme} />
            <RealtimeFeed isDark={isDark} theme={theme} />
          </Box>

          {/* ── Bottom: reply rate trend ── */}
          <Section
            title="Reply Rate Trend"
            subtitle="Daily reply rate movement"
            color="#34d399" isDark={isDark} theme={theme}
            action={<Legend items={[{ label: 'Reply Rate', color: '#34d399' }]} />}
          >
            <Box sx={{ height: 140 }}>
              <LineChart
                series={[series.replies]}
                colors={['#34d399']}
                labels={['Replies']}
                isDark={isDark}
                height={140}
              />
            </Box>
          </Section>

        </Box>
      </Box>
    </Box>
  );
}
