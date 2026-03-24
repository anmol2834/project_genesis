'use client';

import { useEffect, useState, useRef } from 'react';
import { Box, Typography, useTheme, alpha } from '@mui/material';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import ReplyRoundedIcon from '@mui/icons-material/ReplyRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';

const STATS = [
  { label: 'Emails Processed', value: 2847, icon: EmailRoundedIcon,       color: '#818cf8', darkBg: 'rgba(99,102,241,0.12)',  lightBg: 'rgba(67,56,202,0.07)',  trend: '+12%', sub: 'vs last week' },
  { label: 'Replies Received',  value: 384,  icon: ReplyRoundedIcon,       color: '#34d399', darkBg: 'rgba(16,185,129,0.12)', lightBg: 'rgba(5,150,105,0.07)',  trend: '+8%',  sub: 'vs last week' },
  { label: 'AI Responses',      value: 271,  icon: AutoAwesomeRoundedIcon, color: '#c084fc', darkBg: 'rgba(139,92,246,0.12)', lightBg: 'rgba(124,58,237,0.07)', trend: '+24%', sub: 'auto-generated' },
  { label: 'Active Campaigns',  value: 6,    icon: CampaignRoundedIcon,    color: '#fbbf24', darkBg: 'rgba(245,158,11,0.12)', lightBg: 'rgba(217,119,6,0.07)',  trend: '2 live', sub: 'running now' },
];

// Gradient top-border colors per card
const CARD_ACCENTS = ['#818cf8', '#34d399', '#c084fc', '#fbbf24'];

function CountUp({ target, duration = 1400 }: { target: number; duration?: number }) {
  const [count, setCount] = useState(0);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      setCount(Math.round((1 - Math.pow(1 - p, 3)) * target));
      if (p < 1) frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => { if (frameRef.current) cancelAnimationFrame(frameRef.current); };
  }, [target, duration]);

  return <>{count.toLocaleString()}</>;
}

export default function StatsOverview() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', lg: 'repeat(4, 1fr)' }, gap: 1.5 }}>
      {STATS.map((stat, i) => {
        const Icon = stat.icon;
        return (
          <Box
            key={stat.label}
            sx={{
              p: { xs: 1.75, sm: 2.25 },
              borderRadius: '14px',
              border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : theme.palette.divider}`,
              background: isDark ? stat.darkBg : stat.lightBg,
              position: 'relative',
              overflow: 'hidden',
              cursor: 'default',
              transition: 'transform 0.2s ease, box-shadow 0.2s ease',
              '&:hover': {
                transform: 'translateY(-2px)',
                boxShadow: isDark
                  ? `0 12px 32px rgba(0,0,0,0.4), 0 0 0 1px ${alpha(stat.color, 0.3)}`
                  : `0 12px 32px rgba(15,23,42,0.1), 0 0 0 1px ${alpha(stat.color, 0.25)}`,
              },
              // Colored top accent line
              '&::before': {
                content: '""',
                position: 'absolute',
                top: 0, left: 0, right: 0,
                height: '2px',
                background: `linear-gradient(90deg, ${CARD_ACCENTS[i]}, ${alpha(CARD_ACCENTS[i], 0.3)})`,
              },
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1.75 }}>
              <Box sx={{
                width: 36, height: 36, borderRadius: '10px',
                background: isDark ? alpha(stat.color, 0.2) : alpha(stat.color, 0.15),
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: `1px solid ${alpha(stat.color, isDark ? 0.3 : 0.2)}`,
              }}>
                <Icon sx={{ fontSize: 18, color: stat.color }} />
              </Box>
              <Box sx={{
                display: 'flex', alignItems: 'center', gap: 0.4,
                px: 0.75, py: 0.3, borderRadius: '6px',
                background: alpha('#34d399', isDark ? 0.15 : 0.1),
              }}>
                <TrendingUpRoundedIcon sx={{ fontSize: 10, color: '#34d399' }} />
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: '#34d399' }}>
                  {stat.trend}
                </Typography>
              </Box>
            </Box>

            <Typography sx={{
              fontSize: { xs: '1.5rem', sm: '1.75rem' },
              fontWeight: 800, letterSpacing: '-0.04em', lineHeight: 1,
              color: isDark ? '#fff' : theme.palette.text.primary,
            }}>
              <CountUp target={stat.value} />
            </Typography>
            <Typography sx={{ fontSize: '0.73rem', fontWeight: 600, mt: 0.5, color: isDark ? 'rgba(255,255,255,0.7)' : theme.palette.text.secondary }}>
              {stat.label}
            </Typography>
            <Typography sx={{ fontSize: '0.63rem', color: isDark ? 'rgba(255,255,255,0.35)' : theme.palette.text.disabled, mt: 0.2 }}>
              {stat.sub}
            </Typography>
          </Box>
        );
      })}
    </Box>
  );
}
