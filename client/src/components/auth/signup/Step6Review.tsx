'use client';

import { Box, Typography, Button, useTheme, alpha, CircularProgress, Alert } from '@mui/material';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import { motion } from 'framer-motion';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { lightGradients, darkGradients } from '@/theme/palette';
import { useAuth } from '@/contexts/AuthContext';
import { useSignup, useGetProfile } from '@/hooks/mutations/useAuthMutations';
import type { Step1Data } from './Step1Account';
import type { Step3Data } from './Step3Business';
import type { Step4Data } from './Step4AIContext';

interface Props {
  step1: Step1Data;
  step3: Step3Data;
  step4: Step4Data;
  emailConnected: boolean;
  onBack: () => void;
}

export default function Step6Review({ step1, step3, step4, emailConnected, onBack }: Props) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const router = useRouter();
  
  // Auth context and mutations
  const { setAuthData } = useAuth();
  const signupMutation = useSignup();
  const getProfileMutation = useGetProfile();
  
  const [done, setDone] = useState(false);

  const handleLaunch = async () => {
    try {
      // Step 1: Signup and get tokens
      const signupResponse = await signupMutation.mutateAsync({
        full_name: step1.fullName,
        email: step1.email,
        password: step1.password,
        business_name: step3.businessName,
        business_type: step3.businessType,
        industries: step3.industries,
        country: step3.country,
        timezone: step3.timezone,
        business_description: step4.description,
        target_audience: step4.audience,
        communication_tone: step4.tone,
        use_cases: step4.useCases,
      });

      // Step 2: Store tokens in localStorage immediately so apiClient can use them
      localStorage.setItem('auth_tokens', JSON.stringify(signupResponse.tokens));
      const expiryTimestamp = Date.now() + (signupResponse.tokens.expires_in * 1000);
      localStorage.setItem('auth_token_expiry', expiryTimestamp.toString());

      // Step 3: Fetch full user profile (apiClient will now have the token)
      const userProfile = await getProfileMutation.mutateAsync();

      // Step 4: Update auth context with user data and tokens
      setAuthData(userProfile, signupResponse.tokens);

      // Step 5: Show success state
      setDone(true);
    } catch (error) {
      // Error is already handled by React Query and displayed via signupMutation.error
      console.error('[Step6Review] Signup failed:', error);
    }
  };

  const rows: { label: string; value: string }[] = [
    { label: 'Name',      value: step1.fullName },
    { label: 'Email',     value: step1.email },
    { label: 'Business',  value: step3.businessName || '—' },
    { label: 'Type',      value: step3.businessType || '—' },
    { label: 'Country',   value: step3.country || '—' },
    { label: 'Tone',      value: step4.tone ? step4.tone.charAt(0).toUpperCase() + step4.tone.slice(1) : '—' },
    { label: 'Use-cases', value: step4.useCases.length ? step4.useCases.join(', ') : '—' },
    { label: 'Inbox',     value: emailConnected ? 'Connected' : 'Not connected' },
  ];

  const isLoading = signupMutation.isPending || getProfileMutation.isPending;
  const errorMsg = signupMutation.error?.message || getProfileMutation.error?.message || '';

  if (done) {
    return (
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}>
        <Box sx={{ textAlign: 'center', py: 2 }}>
          <motion.div animate={{ scale: [0.8, 1.1, 1] }} transition={{ duration: 0.5, ease: 'easeOut' }}>
            <Box sx={{ width: 56, height: 56, borderRadius: '16px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center', mx: 'auto', mb: 2, boxShadow: isDark ? '0 8px 24px rgba(129,140,248,0.30)' : '0 8px 24px rgba(67,56,202,0.22)' }}>
              <BoltRoundedIcon sx={{ color: '#fff', fontSize: 28 }} />
            </Box>
          </motion.div>
          <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1.1rem', mb: 0.75 }}>You're all set!</Typography>
          <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary', mb: 3, lineHeight: 1.6 }}>
            Your AI is initialized and ready.<br />Head to your dashboard to start.
          </Typography>
          <Button
            variant="contained" fullWidth
            onClick={() => router.push('/dashboard')}
            sx={{ minHeight: 40, fontSize: '0.875rem', fontWeight: 600, borderRadius: '8px', background: grad.primary, boxShadow: isDark ? '0 4px 16px rgba(129,140,248,0.22)' : '0 4px 16px rgba(67,56,202,0.16)', '&:hover': { filter: 'brightness(1.07)' } }}
          >
            Go to dashboard
          </Button>
        </Box>
      </motion.div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.3, ease: 'easeOut' }}>
      <Box sx={{ mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1.05rem', mb: 0.4 }}>Review & launch</Typography>
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>Confirm your setup before AI initialization</Typography>
      </Box>

      {/* Summary card */}
      <Box sx={{ borderRadius: '10px', border: `1px solid ${theme.palette.divider}`, overflow: 'hidden', mb: 2 }}>
        {rows.map((row, i) => (
          <Box key={row.label} sx={{ display: 'flex', alignItems: 'center', px: 1.75, py: 0.875, borderBottom: i < rows.length - 1 ? `1px solid ${theme.palette.divider}` : 'none', background: i % 2 === 0 ? alpha(theme.palette.text.primary, isDark ? 0.02 : 0.015) : 'transparent' }}>
            <Typography sx={{ fontSize: '0.72rem', color: 'text.disabled', width: 80, flexShrink: 0, fontWeight: 500 }}>{row.label}</Typography>
            <Typography sx={{ fontSize: '0.8rem', color: row.label === 'Inbox' && emailConnected ? 'success.main' : 'text.primary', fontWeight: row.label === 'Inbox' && emailConnected ? 600 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {row.label === 'Inbox' && emailConnected && <CheckRoundedIcon sx={{ fontSize: 11, mr: 0.5, verticalAlign: 'middle' }} />}
              {row.value}
            </Typography>
          </Box>
        ))}
      </Box>

      {/* AI ready badge */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1.25, borderRadius: '8px', background: alpha(theme.palette.primary.main, isDark ? 0.08 : 0.05), border: `1px solid ${alpha(theme.palette.primary.main, isDark ? 0.16 : 0.10)}`, mb: errorMsg ? 1.5 : 2 }}>
        <AutoAwesomeRoundedIcon sx={{ fontSize: 14, color: 'primary.main', flexShrink: 0 }} />
        <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', lineHeight: 1.4 }}>
          AI will be initialized with your business context and start generating replies immediately.
        </Typography>
      </Box>

      {/* API error */}
      {errorMsg && (
        <Alert 
          severity="error" 
          onClose={() => {
            signupMutation.reset();
            getProfileMutation.reset();
          }}
          sx={{ mb: 2, fontSize: '0.78rem', borderRadius: '8px', py: 0.5 }}
        >
          {errorMsg}
        </Alert>
      )}

      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button 
          onClick={onBack} 
          disabled={isLoading} 
          variant="outlined" 
          sx={{ minHeight: 40, fontSize: '0.8rem', borderRadius: '8px', px: 2, borderColor: alpha(theme.palette.primary.main, 0.3), flexShrink: 0 }}
        >
          Back
        </Button>
        <Button
          onClick={handleLaunch} 
          variant="contained" 
          fullWidth 
          disabled={isLoading}
          startIcon={isLoading ? <CircularProgress size={14} color="inherit" /> : <BoltRoundedIcon sx={{ fontSize: '16px !important' }} />}
          sx={{ minHeight: 40, fontSize: '0.875rem', fontWeight: 600, borderRadius: '8px', background: grad.primary, boxShadow: isDark ? '0 4px 16px rgba(129,140,248,0.22)' : '0 4px 16px rgba(67,56,202,0.16)', '&:hover': { filter: 'brightness(1.07)' }, '&:disabled': { opacity: 0.6 } }}
        >
          {isLoading ? 'Creating account…' : 'Start using AI'}
        </Button>
      </Box>
    </motion.div>
  );
}
