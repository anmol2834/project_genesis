'use client';

import { useEffect, useRef, useState, useCallback, ClipboardEvent, KeyboardEvent } from 'react';
import { Box, Typography, Button, CircularProgress, useTheme, alpha } from '@mui/material';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import { motion, AnimatePresence } from 'framer-motion';
import { lightGradients, darkGradients } from '@/theme/palette';

const OTP_LEN = 6;
const RESEND_SECS = 30;

interface Props {
  email: string;
  onNext: () => void;
  onBack: () => void;
}

export default function Step2OTP({ email, onNext, onBack }: Props) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  const [digits, setDigits] = useState<string[]>(Array(OTP_LEN).fill(''));
  const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle');
  const [countdown, setCountdown] = useState(RESEND_SECS);
  const [canResend, setCanResend] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Countdown timer
  useEffect(() => {
    if (countdown <= 0) { setCanResend(true); return; }
    const t = setTimeout(() => setCountdown(c => c - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown]);

  // Auto-focus first input
  useEffect(() => { inputRefs.current[0]?.focus(); }, []);

  const focusAt = (i: number) => inputRefs.current[Math.max(0, Math.min(OTP_LEN - 1, i))]?.focus();

  const handleChange = useCallback((i: number, val: string) => {
    const ch = val.replace(/\D/g, '').slice(-1);
    const next = [...digits];
    next[i] = ch;
    setDigits(next);
    if (ch && i < OTP_LEN - 1) focusAt(i + 1);
    if (status === 'error') setStatus('idle');
  }, [digits, status]);

  const handleKey = useCallback((i: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace') {
      if (digits[i]) {
        const next = [...digits]; next[i] = ''; setDigits(next);
      } else { focusAt(i - 1); }
    } else if (e.key === 'ArrowLeft') { focusAt(i - 1); }
    else if (e.key === 'ArrowRight') { focusAt(i + 1); }
  }, [digits]);

  const handlePaste = useCallback((e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, OTP_LEN);
    const next = Array(OTP_LEN).fill('');
    pasted.split('').forEach((ch, i) => { next[i] = ch; });
    setDigits(next);
    focusAt(Math.min(pasted.length, OTP_LEN - 1));
  }, []);

  const handleVerify = useCallback(async () => {
    const code = digits.join('');
    if (code.length < OTP_LEN) return;
    setStatus('loading');
    await new Promise(r => setTimeout(r, 1200));
    // Demo: any 6-digit code succeeds
    setStatus('success');
    await new Promise(r => setTimeout(r, 700));
    onNext();
  }, [digits, onNext]);

  const handleResend = useCallback(() => {
    setDigits(Array(OTP_LEN).fill(''));
    setStatus('idle');
    setCountdown(RESEND_SECS);
    setCanResend(false);
    setTimeout(() => inputRefs.current[0]?.focus(), 50);
  }, []);

  const filled = digits.every(d => d !== '');

  const boxColor = {
    idle: theme.palette.divider,
    loading: theme.palette.primary.main,
    error: theme.palette.error.main,
    success: theme.palette.success.main,
  }[status];

  return (
    <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.3, ease: 'easeOut' }}>
      <Box sx={{ mb: 2.5, textAlign: 'center' }}>
        <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1.05rem', mb: 0.4 }}>Check your email</Typography>
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', lineHeight: 1.5 }}>
          We sent a 6-digit code to<br />
          <Box component="span" sx={{ fontWeight: 600, color: 'text.primary' }}>{email}</Box>
        </Typography>
      </Box>

      {/* OTP inputs */}
      <Box sx={{ display: 'flex', gap: { xs: 0.75, sm: 1 }, justifyContent: 'center', mb: 2 }}>
        {digits.map((d, i) => (
          <Box
            key={i}
            component="input"
            ref={(el: HTMLInputElement | null) => { inputRefs.current[i] = el; }}
            type="text"
            inputMode="numeric"
            maxLength={1}
            value={d}
            onChange={e => handleChange(i, e.target.value)}
            onKeyDown={e => handleKey(i, e)}
            onPaste={handlePaste}
            onFocus={e => e.target.select()}
            sx={{
              width: { xs: 40, sm: 44 },
              height: { xs: 44, sm: 48 },
              textAlign: 'center',
              fontSize: '1.1rem',
              fontWeight: 700,
              fontFamily: 'inherit',
              borderRadius: '10px',
              border: `1.5px solid ${d ? boxColor : theme.palette.divider}`,
              background: d
                ? alpha(status === 'error' ? theme.palette.error.main : theme.palette.primary.main, isDark ? 0.10 : 0.06)
                : theme.palette.background.paper,
              color: theme.palette.text.primary,
              outline: 'none',
              transition: 'all 0.18s ease',
              cursor: 'text',
              '&:focus': {
                borderColor: status === 'error' ? theme.palette.error.main : theme.palette.primary.main,
                boxShadow: `0 0 0 3px ${alpha(status === 'error' ? theme.palette.error.main : theme.palette.primary.main, isDark ? 0.16 : 0.10)}`,
              },
            }}
          />
        ))}
      </Box>

      {/* Error message */}
      <AnimatePresence>
        {status === 'error' && (
          <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <Typography sx={{ textAlign: 'center', fontSize: '0.75rem', color: 'error.main', mb: 1.5 }}>
              Incorrect code. Please try again.
            </Typography>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Verify button */}
      <Button
        variant="contained"
        fullWidth
        disabled={!filled || status === 'loading' || status === 'success'}
        onClick={handleVerify}
        sx={{
          minHeight: 40, fontSize: '0.875rem', fontWeight: 600, borderRadius: '8px',
          background: filled ? grad.primary : undefined,
          boxShadow: filled ? (isDark ? '0 4px 16px rgba(129,140,248,0.22)' : '0 4px 16px rgba(67,56,202,0.16)') : 'none',
          '&:hover': { filter: 'brightness(1.07)' },
          '&:disabled': { opacity: 0.45 },
          mb: 1.75,
        }}
      >
        {status === 'loading' ? <CircularProgress size={16} color="inherit" /> :
         status === 'success' ? <CheckCircleRoundedIcon sx={{ fontSize: 18 }} /> : 'Verify email'}
      </Button>

      {/* Resend */}
      <Box sx={{ textAlign: 'center' }}>
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
          Didn't receive it?{' '}
          {canResend ? (
            <Box component="span" onClick={handleResend} sx={{ color: 'primary.main', fontWeight: 600, cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}>
              Resend code
            </Box>
          ) : (
            <Box component="span" sx={{ color: 'text.disabled' }}>Resend in {countdown}s</Box>
          )}
        </Typography>
      </Box>

      <Box sx={{ textAlign: 'center', mt: 1.5 }}>
        <Box component="span" onClick={onBack} sx={{ fontSize: '0.75rem', color: 'text.disabled', cursor: 'pointer', '&:hover': { color: 'text.secondary' } }}>
          ← Change email
        </Box>
      </Box>
    </motion.div>
  );
}
