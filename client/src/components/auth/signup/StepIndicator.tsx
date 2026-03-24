'use client';

import { Box, Typography, useTheme, alpha } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';

const STEPS = [
  'Account',
  'Verify',
  'Business',
  'AI Setup',
  'Email',
  'Review',
];

interface Props {
  current: number; // 1-based
}

export default function StepIndicator({ current }: Props) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const pct = Math.round(((current - 1) / (STEPS.length - 1)) * 100);

  return (
    <Box sx={{ width: '100%', mb: 3 }}>
      {/* Step label + count */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.25 }}>
        <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: 'primary.main' }}>
          {STEPS[current - 1]}
        </Typography>
        <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled' }}>
          {current} / {STEPS.length}
        </Typography>
      </Box>

      {/* Progress track */}
      <Box sx={{ position: 'relative', height: 3, borderRadius: '9999px', background: alpha(theme.palette.primary.main, isDark ? 0.14 : 0.10), overflow: 'hidden' }}>
        <motion.div
          animate={{ width: `${pct === 0 ? 4 : pct}%` }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
          style={{
            position: 'absolute', left: 0, top: 0, height: '100%', borderRadius: 9999,
            background: `linear-gradient(90deg, ${isDark ? '#818cf8' : '#4338ca'}, ${isDark ? '#a78bfa' : '#7c3aed'})`,
          }}
        />
      </Box>

      {/* Dot indicators */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1.25 }}>
        {STEPS.map((label, i) => {
          const stepNum = i + 1;
          const done = stepNum < current;
          const active = stepNum === current;
          return (
            <Box key={label} sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.4 }}>
              <Box
                sx={{
                  width: active ? 7 : 5,
                  height: active ? 7 : 5,
                  borderRadius: '50%',
                  transition: 'all 0.3s ease',
                  background: done
                    ? (isDark ? '#818cf8' : '#4338ca')
                    : active
                      ? (isDark ? '#a78bfa' : '#7c3aed')
                      : alpha(theme.palette.text.disabled, 0.3),
                  boxShadow: active ? `0 0 0 2px ${alpha(isDark ? '#818cf8' : '#4338ca', 0.25)}` : 'none',
                }}
              />
              <Typography
                sx={{
                  fontSize: '0.55rem',
                  color: active ? 'primary.main' : done ? 'text.secondary' : 'text.disabled',
                  fontWeight: active ? 600 : 400,
                  display: { xs: 'none', sm: 'block' },
                  transition: 'color 0.3s ease',
                  whiteSpace: 'nowrap',
                }}
              >
                {label}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
