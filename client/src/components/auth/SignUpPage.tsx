'use client';

import { useState, useCallback } from 'react';
import { Box, IconButton, Typography, useTheme, alpha } from '@mui/material';
import LightModeRoundedIcon from '@mui/icons-material/LightModeRounded';
import DarkModeRoundedIcon from '@mui/icons-material/DarkModeRounded';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import NextLink from 'next/link';
import dynamic from 'next/dynamic';
import { useThemeMode } from '@/providers/AppThemeProvider';
import { lightGradients, darkGradients } from '@/theme/palette';

import StepIndicator from './signup/StepIndicator';
import Step1Account, { type Step1Data } from './signup/Step1Account';
import Step2OTP from './signup/Step2OTP';
import Step3Business, { type Step3Data } from './signup/Step3Business';
import Step4AIContext, { type Step4Data } from './signup/Step4AIContext';
import Step5Email from './signup/Step5Email';
import Step6Review from './signup/Step6Review';

// Lazy-load the heavy visual panel
const SignUpVisual = dynamic(() => import('./SignUpVisual'), { ssr: false });

const TOTAL = 6;

export default function SignUpPage() {
  const { mode, toggleTheme } = useThemeMode();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  const [step, setStep] = useState(1);
  const [emailConnected, setEmailConnected] = useState(false);

  const [step1, setStep1] = useState<Step1Data>({ fullName: '', email: '', password: '', confirmPassword: '' });
  const [step3, setStep3] = useState<Step3Data>({ businessName: '', businessType: '', industries: [], country: 'India', timezone: 'India — Kolkata (UTC+5:30)' });
  const [step4, setStep4] = useState<Step4Data>({ description: '', audience: '', tone: '', useCases: [] });

  const next = useCallback(() => setStep(s => Math.min(s + 1, TOTAL)), []);
  // After OTP (step 2) is verified, back from step 3 goes to step 1 — not back to OTP
  const back = useCallback(() => setStep(s => s === 3 ? 1 : Math.max(s - 1, 1)), []);

  return (
    // Outer shell — full viewport, no overflow
    <Box
      sx={{
        height: '100svh',
        display: 'flex',
        background: theme.palette.background.default,
        overflow: 'hidden',
      }}
    >
      {/* ── Left panel: scrollable form ──────────────────────────────────── */}
      <Box
        sx={{
          flex: '0 0 auto',
          width: { xs: '100%', md: '50%', lg: '45%' },
          display: 'flex',
          flexDirection: 'column',
          height: '100svh',
          overflow: 'hidden',
        }}
      >
        {/* Top bar — sticky inside left panel */}
        <Box
          sx={{
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: { xs: 2.5, sm: 4 },
            py: 2,
            borderBottom: `1px solid ${theme.palette.divider}`,
            background: theme.palette.background.default,
            zIndex: 2,
          }}
        >
          <Box
            component={NextLink}
            href="/"
            sx={{
              display: 'flex', alignItems: 'center', gap: 0.5,
              color: 'text.secondary', fontSize: '0.78rem', fontWeight: 500,
              textDecoration: 'none', transition: 'color 0.18s',
              '&:hover': { color: 'text.primary' },
            }}
          >
            <ArrowBackRoundedIcon sx={{ fontSize: 14 }} />
            Back
          </Box>

          {/* Logo — mobile only */}
          <Box sx={{ display: { xs: 'flex', md: 'none' }, alignItems: 'center', gap: 0.75 }}>
            <Box sx={{ width: 26, height: 26, borderRadius: '7px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <BoltRoundedIcon sx={{ color: '#fff', fontSize: 14 }} />
            </Box>
            <Typography sx={{ fontWeight: 700, fontSize: '0.9rem', letterSpacing: '-0.02em', color: 'text.primary' }}>
              Proxipilot
            </Typography>
          </Box>

          <IconButton
            onClick={toggleTheme}
            size="small"
            sx={{ width: 36, height: 36, color: 'text.secondary', borderRadius: '8px', border: `1px solid ${theme.palette.divider}`, '&:hover': { borderColor: theme.palette.primary.main } }}
          >
            {mode === 'dark'
              ? <LightModeRoundedIcon sx={{ fontSize: 15 }} />
              : <DarkModeRoundedIcon sx={{ fontSize: 15 }} />
            }
          </IconButton>
        </Box>

        {/* Scrollable form area */}
        <Box
          sx={{
            flex: 1,
            overflowY: 'auto',
            px: { xs: 2.5, sm: 5, md: 6, lg: 8 },
            pt: { xs: 2, sm: 3 },
            pb: { xs: 3, sm: 8 },
            // Custom scrollbar
            '&::-webkit-scrollbar': { width: 4 },
            '&::-webkit-scrollbar-track': { background: 'transparent' },
            '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
          }}
        >
          <Box sx={{ width: '100%', maxWidth: 420, mx: 'auto' }}>
            <StepIndicator current={step} />

            <Box sx={{
              p: { xs: 2.5, sm: 3 },
              borderRadius: '14px',
              border: `1px solid ${theme.palette.divider}`,
              background: theme.palette.background.paper,
              boxShadow: isDark ? '0 4px 24px rgba(0,0,0,0.25)' : '0 4px 24px rgba(15,23,42,0.06)',
            }}>
              {step === 1 && <Step1Account key="s1" data={step1} onChange={setStep1} onNext={next} />}
                {step === 2 && <Step2OTP key="s2" email={step1.email} onNext={next} onBack={back} />}
                {step === 3 && <Step3Business key="s3" data={step3} onChange={setStep3} onNext={next} onBack={back} />}
                {step === 4 && <Step4AIContext key="s4" data={step4} onChange={setStep4} onNext={next} onBack={back} />}
                {step === 5 && (
                  <Step5Email key="s5"
                    onNext={() => { setEmailConnected(true); next(); }}
                    onBack={back}
                    onSkip={() => { setEmailConnected(false); next(); }}
                  />
                )}
                {step === 6 && <Step6Review key="s6" step1={step1} step3={step3} step4={step4} emailConnected={emailConnected} onBack={back} />}
            </Box>

            {step === 1 && (
              <Typography sx={{ textAlign: 'center', fontSize: '0.78rem', color: 'text.secondary', mt: 2 }}>
                Already have an account?{' '}
                <Box component={NextLink} href="/sign-in" sx={{ color: 'primary.main', fontWeight: 600, textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}>
                  Sign in
                </Box>
              </Typography>
            )}
          </Box>
        </Box>
      </Box>

      {/* ── Right panel: fixed visual, never scrolls ──────────────────────── */}
      <Box
        sx={{
          display: { xs: 'none', md: 'flex' },
          flex: 1,
          position: 'sticky',
          top: 0,
          height: '100svh',
          borderLeft: `1px solid ${theme.palette.divider}`,
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        <Box sx={{ position: 'relative', zIndex: 1, width: '100%', height: '100%' }}>
          <SignUpVisual currentStep={step} />
        </Box>
      </Box>
    </Box>
  );
}
