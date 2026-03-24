'use client';

import { useCallback, useId } from 'react';
import { Box, Typography, TextField, Button, useTheme, alpha } from '@mui/material';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import { motion } from 'framer-motion';
import { lightGradients, darkGradients } from '@/theme/palette';

const TONES = [
  { key: 'professional', label: 'Professional', desc: 'Formal, clear, business-focused' },
  { key: 'friendly',     label: 'Friendly',     desc: 'Warm, approachable, conversational' },
  { key: 'sales',        label: 'Sales-driven', desc: 'Persuasive, action-oriented' },
  { key: 'custom',       label: 'Custom',        desc: 'AI learns from your writing style' },
];

const USE_CASES = [
  { key: 'sales',     label: 'Sales outreach' },
  { key: 'support',   label: 'Customer support' },
  { key: 'followups', label: 'Follow-ups' },
  { key: 'outreach',  label: 'Cold outreach' },
];

export interface Step4Data {
  description: string;
  audience: string;
  tone: string;
  useCases: string[];
}

interface Props { data: Step4Data; onChange: (d: Step4Data) => void; onNext: () => void; onBack: () => void; }

export default function Step4AIContext({ data, onChange, onNext, onBack }: Props) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const descId = useId(); const audId = useId();

  const set = useCallback((f: keyof Step4Data) => (val: string) => onChange({ ...data, [f]: val }), [data, onChange]);

  const toggleUseCase = useCallback((key: string) => {
    const next = data.useCases.includes(key) ? data.useCases.filter(k => k !== key) : [...data.useCases, key];
    onChange({ ...data, useCases: next });
  }, [data, onChange]);

  const valid = data.description.trim().length >= 10 && data.tone && data.useCases.length > 0;

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      fontSize: '0.875rem', borderRadius: '8px',
      '&.Mui-focused': { boxShadow: `0 0 0 3px ${alpha(theme.palette.primary.main, isDark ? 0.16 : 0.10)}` },
    },
    '& .MuiInputLabel-root': { fontSize: '0.875rem' },
  };

  const chipSx = (active: boolean) => ({
    px: 1.25, py: 0.5, borderRadius: '8px', cursor: 'pointer',
    border: `1px solid ${active ? theme.palette.primary.main : theme.palette.divider}`,
    background: active ? alpha(theme.palette.primary.main, isDark ? 0.14 : 0.07) : 'transparent',
    transition: 'all 0.18s ease',
    '&:hover': { borderColor: theme.palette.primary.main, background: alpha(theme.palette.primary.main, isDark ? 0.10 : 0.05) },
  });

  return (
    <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.3, ease: 'easeOut' }}>
      <Box sx={{ mb: 2.5 }}>
        <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1.05rem', mb: 0.4 }}>AI context setup</Typography>
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>This trains your AI to write perfect replies from day one</Typography>
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <TextField
          id={descId} label="What does your business do?" multiline rows={2}
          value={data.description} onChange={e => set('description')(e.target.value)}
          placeholder="e.g. We help SaaS companies automate their sales outreach..."
          size="small" fullWidth sx={inputSx}
          inputProps={{ maxLength: 200 }}
          helperText={<Box component="span" sx={{ fontSize: '0.68rem', color: 'text.disabled' }}>{data.description.length}/200</Box>}
        />

        <TextField
          id={audId} label="Who are your customers?" value={data.audience}
          onChange={e => set('audience')(e.target.value)}
          placeholder="e.g. B2B SaaS founders, marketing managers..."
          size="small" fullWidth sx={inputSx}
        />

        {/* Tone selector */}
        <Box>
          <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: 'text.secondary', mb: 1, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Communication tone
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0.75 }}>
            {TONES.map(t => (
              <Box key={t.key} onClick={() => set('tone')(t.key)} sx={chipSx(data.tone === t.key)}>
                <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: data.tone === t.key ? 'primary.main' : 'text.primary', lineHeight: 1.2 }}>{t.label}</Typography>
                <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mt: 0.2, lineHeight: 1.3 }}>{t.desc}</Typography>
              </Box>
            ))}
          </Box>
        </Box>

        {/* Use cases */}
        <Box>
          <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: 'text.secondary', mb: 1, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Primary email use-cases
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
            {USE_CASES.map(u => {
              const active = data.useCases.includes(u.key);
              return (
                <Box key={u.key} onClick={() => toggleUseCase(u.key)}
                  sx={{ px: 1.25, py: 0.5, borderRadius: '7px', cursor: 'pointer', border: `1px solid ${active ? theme.palette.primary.main : theme.palette.divider}`, background: active ? alpha(theme.palette.primary.main, isDark ? 0.14 : 0.07) : 'transparent', transition: 'all 0.18s ease', '&:hover': { borderColor: theme.palette.primary.main } }}>
                  <Typography sx={{ fontSize: '0.78rem', fontWeight: active ? 600 : 400, color: active ? 'primary.main' : 'text.secondary' }}>{u.label}</Typography>
                </Box>
              );
            })}
          </Box>
        </Box>

        <Box sx={{ display: 'flex', gap: 1, mt: 0.25 }}>
          <Button onClick={onBack} variant="outlined" sx={{ minHeight: 40, fontSize: '0.8rem', borderRadius: '8px', px: 2, borderColor: alpha(theme.palette.primary.main, 0.3), flexShrink: 0 }}>
            <ArrowBackRoundedIcon sx={{ fontSize: 16 }} />
          </Button>
          <Button
            onClick={onNext} variant="contained" fullWidth disabled={!valid}
            endIcon={<ArrowForwardRoundedIcon sx={{ fontSize: '16px !important' }} />}
            sx={{
              minHeight: 40, fontSize: '0.875rem', fontWeight: 600, borderRadius: '8px',
              background: valid ? grad.primary : undefined,
              boxShadow: valid ? (isDark ? '0 4px 16px rgba(129,140,248,0.22)' : '0 4px 16px rgba(67,56,202,0.16)') : 'none',
              '&:hover': { filter: 'brightness(1.07)' }, '&:disabled': { opacity: 0.45 },
            }}
          >
            Continue
          </Button>
        </Box>
      </Box>
    </motion.div>
  );
}
