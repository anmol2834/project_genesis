'use client';

import { useState, useCallback, useId } from 'react';
import { Box, Typography, TextField, Button, IconButton, InputAdornment, useTheme, alpha } from '@mui/material';
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded';
import VisibilityOffRoundedIcon from '@mui/icons-material/VisibilityOffRounded';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';
import { motion } from 'framer-motion';
import { lightGradients, darkGradients } from '@/theme/palette';

export interface Step1Data {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

interface Props {
  data: Step1Data;
  onChange: (d: Step1Data) => void;
  onNext: () => void;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function Step1Account({ data, onChange, onNext }: Props) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const [showPw, setShowPw] = useState(false);
  const [showCpw, setShowCpw] = useState(false);
  const [touched, setTouched] = useState({ fullName: false, email: false, password: false, confirmPassword: false });

  const nameId = useId(); const emailId = useId(); const pwId = useId(); const cpwId = useId();

  const errors = {
    fullName: touched.fullName && !data.fullName.trim() ? 'Full name is required' : '',
    email: touched.email && !EMAIL_RE.test(data.email) ? 'Enter a valid email' : '',
    password: touched.password && data.password.length < 8 ? 'Minimum 8 characters' : '',
    confirmPassword: touched.confirmPassword && data.password !== data.confirmPassword ? 'Passwords do not match' : '',
  };

  const valid = data.fullName.trim() && EMAIL_RE.test(data.email) && data.password.length >= 8 && data.password === data.confirmPassword;

  const touch = useCallback((f: keyof typeof touched) => () => setTouched(p => ({ ...p, [f]: true })), []);

  const set = useCallback((f: keyof Step1Data) => (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...data, [f]: e.target.value });
  }, [data, onChange]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTouched({ fullName: true, email: true, password: true, confirmPassword: true });
    if (valid) onNext();
  };

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      fontSize: '0.875rem', borderRadius: '8px',
      '&.Mui-focused': { boxShadow: `0 0 0 3px ${alpha(theme.palette.primary.main, isDark ? 0.16 : 0.10)}` },
    },
    '& .MuiInputLabel-root': { fontSize: '0.875rem' },
    '& .MuiFormHelperText-root': { fontSize: '0.7rem', mx: 0, mt: 0.4 },
  };

  return (
    <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.3, ease: 'easeOut' }}>
      <Box sx={{ mb: 2.5 }}>
        <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1.05rem', mb: 0.4 }}>Create your account</Typography>
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>Start your AI email automation journey</Typography>
      </Box>

      <Box component="form" onSubmit={handleSubmit} noValidate sx={{ display: 'flex', flexDirection: 'column', gap: 1.75 }}>
        <TextField id={nameId} label="Full name" value={data.fullName} onChange={set('fullName')} onBlur={touch('fullName')} error={!!errors.fullName} helperText={errors.fullName} size="small" fullWidth sx={inputSx} autoComplete="name" autoFocus />
        <TextField id={emailId} label="Work email" type="email" value={data.email} onChange={set('email')} onBlur={touch('email')} error={!!errors.email} helperText={errors.email} size="small" fullWidth sx={inputSx} autoComplete="email" />
        <TextField
          id={pwId} label="Password" type={showPw ? 'text' : 'password'}
          value={data.password} onChange={set('password')} onBlur={touch('password')}
          error={!!errors.password} helperText={errors.password || 'Minimum 8 characters'}
          size="small" fullWidth sx={inputSx} autoComplete="new-password"
          InputProps={{ endAdornment: (
            <InputAdornment position="end">
              <IconButton onClick={() => setShowPw(p => !p)} size="small" tabIndex={-1} sx={{ color: 'text.disabled' }}>
                {showPw ? <VisibilityOffRoundedIcon sx={{ fontSize: 15 }} /> : <VisibilityRoundedIcon sx={{ fontSize: 15 }} />}
              </IconButton>
            </InputAdornment>
          )}}
        />
        <TextField
          id={cpwId} label="Confirm password" type={showCpw ? 'text' : 'password'}
          value={data.confirmPassword} onChange={set('confirmPassword')} onBlur={touch('confirmPassword')}
          error={!!errors.confirmPassword} helperText={errors.confirmPassword}
          size="small" fullWidth sx={inputSx} autoComplete="new-password"
          InputProps={{ endAdornment: (
            <InputAdornment position="end">
              <IconButton onClick={() => setShowCpw(p => !p)} size="small" tabIndex={-1} sx={{ color: 'text.disabled' }}>
                {showCpw ? <VisibilityOffRoundedIcon sx={{ fontSize: 15 }} /> : <VisibilityRoundedIcon sx={{ fontSize: 15 }} />}
              </IconButton>
            </InputAdornment>
          )}}
        />

        <Button
          type="submit"
          variant="contained"
          fullWidth
          endIcon={<ArrowForwardRoundedIcon sx={{ fontSize: '16px !important' }} />}
          sx={{
            mt: 0.5, minHeight: 40, fontSize: '0.875rem', fontWeight: 600, borderRadius: '8px',
            background: valid ? grad.primary : undefined,
            boxShadow: valid ? (isDark ? '0 4px 16px rgba(129,140,248,0.22)' : '0 4px 16px rgba(67,56,202,0.16)') : 'none',
            '&:hover': { filter: 'brightness(1.07)' },
            '&:disabled': { opacity: 0.45 },
          }}
        >
          Continue
        </Button>
      </Box>
    </motion.div>
  );
}
