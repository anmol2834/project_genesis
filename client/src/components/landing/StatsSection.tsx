'use client';

import { useEffect, useRef, useState } from 'react';
import { Box, Typography, useTheme, alpha } from '@mui/material';
import { useInView } from 'framer-motion';
import { FadeUp } from './motion';
import { lightGradients, darkGradients } from '@/theme/palette';

const STATS = [
  { value: 87,  suffix: '%',  label: 'Faster processing',    desc: 'vs. legacy polling systems'       },
  { value: 25,  suffix: 'ms', label: 'End-to-end pipeline',  desc: 'Email arrival to reply ready'     },
  { value: 10,  suffix: 'K+', label: 'Concurrent users',     desc: 'Without degradation'              },
  { value: 80,  suffix: '%',  label: 'API cost reduction',   desc: 'Smart caching & batching'         },
];

function AnimatedCounter({ target, suffix, duration = 1600 }: { target: number; suffix: string; duration?: number }) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });

  useEffect(() => {
    if (!inView) return;
    const start = performance.now();
    const tick = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(eased * target));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [inView, target, duration]);

  return <span ref={ref}>{count}{suffix}</span>;
}

export default function StatsSection() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  return (
    <Box
      component="section"
      sx={{
        py: { xs: 7, sm: 10, md: 14 },
        px: { xs: 2, sm: 3, md: 4 },
        background: isDark
          ? `linear-gradient(135deg, ${alpha('#818cf8', 0.06)} 0%, ${alpha('#a78bfa', 0.04)} 100%)`
          : `linear-gradient(135deg, ${alpha('#4338ca', 0.03)} 0%, ${alpha('#7c3aed', 0.02)} 100%)`,
        borderTop: `1px solid ${theme.palette.divider}`,
        borderBottom: `1px solid ${theme.palette.divider}`,
      }}
    >
      <Box sx={{ maxWidth: 1200, mx: 'auto' }}>
        <FadeUp>
          <Box sx={{ textAlign: 'center', mb: { xs: 5, sm: 6, md: 8 } }}>
            <Typography variant="overline" sx={{ color: 'primary.main', mb: 1, display: 'block' }}>
              By the numbers
            </Typography>
            <Typography
              variant="h2"
              sx={{ fontSize: { xs: 'clamp(1.5rem, 6vw, 2rem)', md: 'clamp(1.6rem, 4vw, 2.5rem)' } }}
            >
              Built for{' '}
              <Box component="span" sx={{ background: grad.primary, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                scale
              </Box>
            </Typography>
          </Box>
        </FadeUp>

        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: { xs: 1.5, sm: 2, md: 3 } }}>
          {STATS.map((stat, i) => (
            <FadeUp key={stat.label} delay={i * 0.07}>
              <Box
                sx={{
                  p: { xs: 2, sm: 2.5, md: 3 },
                  borderRadius: { xs: '12px', sm: '16px' },
                  textAlign: 'center',
                  border: `1px solid ${theme.palette.divider}`,
                  background: theme.palette.background.paper,
                  transition: 'all 0.2s ease',
                  '&:hover': { boxShadow: theme.shadows[3], transform: 'translateY(-2px)' },
                }}
              >
                <Typography
                  sx={{
                    fontSize: { xs: 'clamp(1.6rem, 7vw, 2.2rem)', md: 'clamp(2rem, 4vw, 2.8rem)' },
                    fontWeight: 800, lineHeight: 1, mb: 0.75,
                    background: grad.primary,
                    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
                  }}
                >
                  <AnimatedCounter target={stat.value} suffix={stat.suffix} />
                </Typography>
                <Typography sx={{ mb: 0.4, fontWeight: 600, fontSize: { xs: '0.75rem', sm: '0.875rem' }, color: 'text.primary' }}>
                  {stat.label}
                </Typography>
                <Typography sx={{ color: 'text.disabled', fontSize: { xs: '0.68rem', sm: '0.75rem' } }}>
                  {stat.desc}
                </Typography>
              </Box>
            </FadeUp>
          ))}
        </Box>
      </Box>
    </Box>
  );
}
