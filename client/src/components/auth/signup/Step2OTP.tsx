'use client';

import { useEffect, useRef, useState, useCallback, ClipboardEvent, KeyboardEvent } from 'react';
import { Box, Typography, Button, CircularProgress, useTheme, alpha } from '@mui/material';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import { motion, AnimatePresence } from 'framer-motion';
import { lightGradients, darkGradients } from '@/theme/palette';
import { useSendOtp, useVerifyOtp } from '@/hooks/mutations/useAuthMutations';

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
  const [errorMsg, setErrorMsg] = useState('');
  const [countdown, setCountdown] = useState(RESEND_SECS);
  const [canResend, setCanResend] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  const sendOtp   = useSendOtp();
  const verifyOtp = useVerifyOtp();

  const isPending = verifyOtp.isPending;
  const isSuccess = verifyOtp.isSuccess;

  // Send OTP as soon as the step mounts
  useEffect(() => {
    sendOtp.mutate({ email });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Countdown timer
  useEffect(() => {
    if (countdown <= 0) { setCanResend(true); return; }
    const t = setTimeout(() => setCountdown(c => c - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown]);

  // Auto-focus first input
  useEffect(() => { inputRefs.current[0]?.focus(); }, []);

  const focusAt = (i: number) =>
    inputRefs.current[Math.max(0, Math.min(OTP_LEN - 1, i))]?.focus();

  const handleChange = useCallback((i: number, val: string) => {
    const ch = val.replace(/\D/g, '').slice(-1);
    const next = [...digits];
    next[i] = ch;
    setDigits(next);
    if (ch && i < OTP_LEN - 1) focusAt(i + 1);
    setErrorMsg('');
  }, [digits]);

  const handleKey = useCallback((i: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace') {
      if (digits[i]) {
        const next = [...digits]; next[i] = ''; setDigits(next);
      } else { focusAt(i - 1); }
    } else if (e.key === 'ArrowLeft')  { focusAt(i - 1); }
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

  const handleVerify = useCallback(() => {
    const code = digits.join('');
    if (code.length < OTP_LEN) return;
    setErrorMsg('');
    verifyOtp.mutate(
      { email, code },
      {
        onSuccess: () => {
          // brief success pause then advance
          setTimeout(onNext, 600);
        },
        onError: (err) => {
          setErrorMsg(err.message ?? 'Invalid or expired code. Please try again.');
          setDigits(Array(OTP_LEN).fill(''));
          setTimeout(() => inputRefs.current[0]?.focus(), 50);
        },
      },
    );
  }, [digits, email, verifyOtp, onNext]);

  const handleResend = useCallback(() => {
    setDigits(Array(OTP_LEN).fill(''));
    setErrorMsg('');
    setCountdown(RESEND_SECS);
    setCanResend(false);
    sendOtp.mutate({ email });
    setTimeout(() => inputRefs.current[0]?.focus(), 50);
  }, [email, sendOtp]);

  const filled = digits.every(d => d !== '');

  // Derive border/bg colour from state
  const activeColor = errorMsg
    ? theme.palette.error.main
    : isSuccess
      ? theme.palette.success.main
      : theme.palette.primary.main;

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
    >
      <Box sx={{ mb: 2.5, textAlign: 'center' }}>
        <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1.05rem', mb: 0.4 }}>
          Check your email
        </Typography>
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
            disabled={isPending || isSuccess}
            sx={{
              width: { xs: 40, sm: 44 },
              height: { xs: 44, sm: 48 },
              textAlign: 'center',
              fontSize: '1.1rem',
              fontWeight: 700,
              fontFamily: 'inherit',
              borderRadius: '10px',
              border: `1.5px solid ${d ? activeColor : theme.palette.divider}`,
              background: d
                ? alpha(activeColor, isDark ? 0.10 : 0.06)
                : theme.palette.background.paper,
              color: theme.palette.text.primary,
              outline: 'none',
              transition: 'all 0.18s ease',
              cursor: isPending || isSuccess ? 'not-allowed' : 'text',
              opacity: isPending || isSuccess ? 0.7 : 1,
              '&:focus': {
                borderColor: activeColor,
                boxShadow: `0 0 0 3px ${alpha(activeColor, isDark ? 0.16 : 0.10)}`,
              },
            }}
          />
        ))}
      </Box>

      {/* Error message */}
      <AnimatePresence>
        {errorMsg && (
          <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <Typography sx={{ textAlign: 'center', fontSize: '0.75rem', color: 'error.main', mb: 1.5 }}>
              {errorMsg}
            </Typography>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Verify button */}
      <Button
        variant="contained"
        fullWidth
        disabled={!filled || isPending || isSuccess}
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
        {isPending
          ? <CircularProgress size={16} color="inherit" />
          : isSuccess
            ? <CheckCircleRoundedIcon sx={{ fontSize: 18 }} />
            : 'Verify email'}
      </Button>

      {/* Resend */}
      <Box sx={{ textAlign: 'center' }}>
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
          Didn't receive it?{' '}
          {canResend ? (
            <Box
              component="span"
              onClick={handleResend}
              sx={{ color: 'primary.main', fontWeight: 600, cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
            >
              {sendOtp.isPending ? 'Sending…' : 'Resend code'}
            </Box>
          ) : (
            <Box component="span" sx={{ color: 'text.disabled' }}>Resend in {countdown}s</Box>
          )}
        </Typography>
      </Box>

      <Box sx={{ textAlign: 'center', mt: 1.5 }}>
        <Box
          component="span"
          onClick={onBack}
          sx={{ fontSize: '0.75rem', color: 'text.disabled', cursor: 'pointer', '&:hover': { color: 'text.secondary' } }}
        >
          ← Change email
        </Box>
      </Box>
    </motion.div>
  );
}
