'use client';

import { useCallback, useId } from 'react';
import { Box, Typography, TextField, Button, MenuItem, useTheme, alpha, Autocomplete, Chip } from '@mui/material';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';
import { lightGradients, darkGradients } from '@/theme/palette';

const BUSINESS_TYPES = ['SaaS', 'Agency', 'E-commerce', 'Freelancer', 'Startup', 'Enterprise', 'Consulting', 'Non-profit', 'Other'];

const INDUSTRIES = ['Technology', 'Marketing', 'Sales', 'Finance', 'Healthcare', 'Education', 'Legal', 'Real Estate', 'Retail', 'Media', 'Logistics', 'HR & Recruiting'];

const COUNTRIES = [
  'India', 'United States', 'United Kingdom', 'Canada', 'Australia',
  'Germany', 'France', 'Netherlands', 'Singapore', 'Brazil', 'Mexico',
  'Spain', 'Italy', 'Japan', 'South Korea', 'UAE', 'South Africa',
  'Nigeria', 'Pakistan', 'Bangladesh', 'Other',
];

// Human-readable: "Country — City (UTC±X:XX)"
const TIMEZONES = [
  'India — Kolkata (UTC+5:30)',
  'United States — New York (UTC-5:00)',
  'United States — Chicago (UTC-6:00)',
  'United States — Denver (UTC-7:00)',
  'United States — Los Angeles (UTC-8:00)',
  'United States — Anchorage (UTC-9:00)',
  'United States — Honolulu (UTC-10:00)',
  'United Kingdom — London (UTC+0:00)',
  'Canada — Toronto (UTC-5:00)',
  'Canada — Vancouver (UTC-8:00)',
  'Australia — Sydney (UTC+10:00)',
  'Australia — Melbourne (UTC+10:00)',
  'Australia — Perth (UTC+8:00)',
  'Germany — Berlin (UTC+1:00)',
  'France — Paris (UTC+1:00)',
  'Netherlands — Amsterdam (UTC+1:00)',
  'Spain — Madrid (UTC+1:00)',
  'Italy — Rome (UTC+1:00)',
  'Sweden — Stockholm (UTC+1:00)',
  'Poland — Warsaw (UTC+1:00)',
  'Finland — Helsinki (UTC+2:00)',
  'Greece — Athens (UTC+2:00)',
  'South Africa — Johannesburg (UTC+2:00)',
  'Egypt — Cairo (UTC+2:00)',
  'Russia — Moscow (UTC+3:00)',
  'Saudi Arabia — Riyadh (UTC+3:00)',
  'UAE — Dubai (UTC+4:00)',
  'Pakistan — Karachi (UTC+5:00)',
  'Bangladesh — Dhaka (UTC+6:00)',
  'Thailand — Bangkok (UTC+7:00)',
  'Vietnam — Ho Chi Minh (UTC+7:00)',
  'Indonesia — Jakarta (UTC+7:00)',
  'China — Beijing (UTC+8:00)',
  'Singapore — Singapore (UTC+8:00)',
  'Malaysia — Kuala Lumpur (UTC+8:00)',
  'Philippines — Manila (UTC+8:00)',
  'South Korea — Seoul (UTC+9:00)',
  'Japan — Tokyo (UTC+9:00)',
  'New Zealand — Auckland (UTC+12:00)',
  'Brazil — São Paulo (UTC-3:00)',
  'Argentina — Buenos Aires (UTC-3:00)',
  'Mexico — Mexico City (UTC-6:00)',
  'Nigeria — Lagos (UTC+1:00)',
  'Kenya — Nairobi (UTC+3:00)',
];

export interface Step3Data {
  businessName: string;
  businessType: string;
  industries: string[];
  country: string;
  timezone: string;
}

interface Props { data: Step3Data; onChange: (d: Step3Data) => void; onNext: () => void; onBack: () => void; }

export default function Step3Business({ data, onChange, onNext, onBack }: Props) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const bnId = useId();

  const set = useCallback((f: keyof Step3Data) => (val: string | string[]) => onChange({ ...data, [f]: val }), [data, onChange]);

  const valid = data.businessName.trim() && data.businessType && data.country && data.timezone;

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      fontSize: '0.875rem', borderRadius: '8px',
      '&.Mui-focused': { boxShadow: `0 0 0 3px ${alpha(theme.palette.primary.main, isDark ? 0.16 : 0.10)}` },
    },
    '& .MuiInputLabel-root': { fontSize: '0.875rem' },
    '& .MuiFormHelperText-root': { fontSize: '0.7rem', mx: 0, mt: 0.4 },
    '& .MuiSelect-select': { fontSize: '0.875rem' },
  };

  return (
    <Box>
      <Box sx={{ mb: 2.5 }}>
        <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1.05rem', mb: 0.4 }}>Your business</Typography>
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>Helps AI understand your context from day one</Typography>
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.75 }}>
        <TextField
          id={bnId} label="Business name" value={data.businessName}
          onChange={e => set('businessName')(e.target.value)}
          size="small" fullWidth sx={inputSx} autoFocus
        />

        <TextField select label="Business type" value={data.businessType} onChange={e => set('businessType')(e.target.value)} size="small" fullWidth sx={inputSx}>
          {BUSINESS_TYPES.map(t => <MenuItem key={t} value={t} sx={{ fontSize: '0.875rem' }}>{t}</MenuItem>)}
        </TextField>

        <Autocomplete
          multiple
          options={INDUSTRIES}
          value={data.industries}
          onChange={(_, v) => set('industries')(v)}
          size="small"
          renderTags={(val, getTagProps) =>
            val.map((opt, i) => (
              <Chip {...getTagProps({ index: i })} key={opt} label={opt} size="small"
                sx={{ fontSize: '0.7rem', height: 22, '& .MuiChip-deleteIcon': { fontSize: 13 } }} />
            ))
          }
          renderInput={(params) => (
            <TextField {...params} label="Industry (optional)" placeholder="Select industries" sx={inputSx} />
          )}
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '0.875rem', '&.Mui-focused': { boxShadow: `0 0 0 3px ${alpha(theme.palette.primary.main, isDark ? 0.16 : 0.10)}` } } }}
        />

        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
          <TextField select label="Country" value={data.country} onChange={e => set('country')(e.target.value)} size="small" fullWidth sx={inputSx}>
            {COUNTRIES.map(c => <MenuItem key={c} value={c} sx={{ fontSize: '0.875rem' }}>{c}</MenuItem>)}
          </TextField>

          <TextField select label="Timezone" value={data.timezone} onChange={e => set('timezone')(e.target.value)} size="small" fullWidth sx={inputSx}
            SelectProps={{ MenuProps: { PaperProps: { sx: { maxHeight: 280 } } } }}
          >
            {TIMEZONES.map(t => (
              <MenuItem key={t} value={t} sx={{ fontSize: '0.8rem', whiteSpace: 'normal', lineHeight: 1.4, py: 0.75 }}>
                {t}
              </MenuItem>
            ))}
          </TextField>
        </Box>

        <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
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
    </Box>
  );
}
