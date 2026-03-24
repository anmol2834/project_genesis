'use client';

import { useState } from 'react';
import React from 'react';
import { Box, Typography, Button, useTheme, alpha } from '@mui/material';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import { motion } from 'framer-motion';
import { lightGradients, darkGradients } from '@/theme/palette';

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}

function OutlookIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect x="1" y="4" width="14" height="16" rx="2" fill="#0078D4"/>
      <path d="M7 8.5C5.34 8.5 4 9.84 4 11.5s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z" fill="white"/>
      <path d="M15 4h6a2 2 0 012 2v12a2 2 0 01-2 2h-6V4z" fill="#0058A3"/>
      <path d="M15 10h8M15 14h8" stroke="white" strokeWidth="1.5"/>
    </svg>
  );
}

const BENEFITS = [
  'AI replies generated instantly on new emails',
  'Real-time inbox sync across all devices',
  'Smart filtering — only real conversations',
];

interface Props { onNext: () => void; onBack: () => void; onSkip: () => void; }

export default function Step5Email({ onNext, onBack, onSkip }: Props) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const [connecting, setConnecting] = useState<'gmail' | 'outlook' | null>(null);
  const [connected, setConnected] = useState<'gmail' | 'outlook' | null>(null);

  const handleConnect = async (provider: 'gmail' | 'outlook') => {
    setConnecting(provider);
    await new Promise(r => setTimeout(r, 1400));
    setConnecting(null);
    setConnected(provider);
  };

  const providerBtn = (provider: 'gmail' | 'outlook', label: string, Icon: () => React.ReactElement) => {
    const isConnected = connected === provider;
    const isConnecting = connecting === provider;
    return (
      <Button
        variant="outlined"
        fullWidth
        disabled={!!connecting || !!connected}
        onClick={() => handleConnect(provider)}
        startIcon={isConnecting ? undefined : isConnected ? <CheckRoundedIcon sx={{ fontSize: 15, color: 'success.main' }} /> : <Icon />}
        sx={{
          minHeight: 40, fontSize: '0.82rem', fontWeight: 500, borderRadius: '8px',
          borderColor: isConnected ? theme.palette.success.main : theme.palette.divider,
          color: isConnected ? 'success.main' : 'text.primary',
          background: isConnected ? alpha(theme.palette.success.main, isDark ? 0.08 : 0.05) : 'transparent',
          '&:hover': { borderColor: theme.palette.primary.main, background: alpha(theme.palette.primary.main, isDark ? 0.06 : 0.04) },
          '&:disabled': { opacity: isConnected ? 1 : 0.5 },
          transition: 'all 0.2s ease',
        }}
      >
        {isConnecting ? 'Connecting…' : isConnected ? `${label} connected` : `Connect ${label}`}
      </Button>
    );
  };

  return (
    <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.3, ease: 'easeOut' }}>
      <Box sx={{ mb: 2.5 }}>
        <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1.05rem', mb: 0.4 }}>Connect your inbox</Typography>
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>Optional — you can always connect later from settings</Typography>
      </Box>

      {/* Benefits */}
      <Box sx={{ p: 1.75, borderRadius: '10px', background: alpha(theme.palette.primary.main, isDark ? 0.07 : 0.04), border: `1px solid ${alpha(theme.palette.primary.main, isDark ? 0.14 : 0.09)}`, mb: 2.5 }}>
        {BENEFITS.map((b, i) => (
          <Box key={i} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: i < BENEFITS.length - 1 ? 1 : 0 }}>
            <Box sx={{ width: 16, height: 16, borderRadius: '50%', background: alpha(theme.palette.primary.main, isDark ? 0.20 : 0.12), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, mt: '1px' }}>
              <CheckRoundedIcon sx={{ fontSize: 10, color: 'primary.main' }} />
            </Box>
            <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', lineHeight: 1.4 }}>{b}</Typography>
          </Box>
        ))}
      </Box>

      {/* Provider buttons */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 2.5 }}>
        {providerBtn('gmail', 'Gmail', GoogleIcon)}
        {providerBtn('outlook', 'Outlook', OutlookIcon)}
      </Box>

      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button onClick={onBack} variant="outlined" sx={{ minHeight: 40, fontSize: '0.8rem', borderRadius: '8px', px: 2, borderColor: alpha(theme.palette.primary.main, 0.3), flexShrink: 0 }}>
          <ArrowBackRoundedIcon sx={{ fontSize: 16 }} />
        </Button>
        {connected ? (
          <Button
            onClick={onNext} variant="contained" fullWidth
            endIcon={<ArrowForwardRoundedIcon sx={{ fontSize: '16px !important' }} />}
            sx={{ minHeight: 40, fontSize: '0.875rem', fontWeight: 600, borderRadius: '8px', background: grad.primary, boxShadow: isDark ? '0 4px 16px rgba(129,140,248,0.22)' : '0 4px 16px rgba(67,56,202,0.16)', '&:hover': { filter: 'brightness(1.07)' } }}
          >
            Continue
          </Button>
        ) : (
          <Button
            onClick={onSkip} variant="outlined" fullWidth
            sx={{ minHeight: 40, fontSize: '0.82rem', fontWeight: 500, borderRadius: '8px', borderColor: alpha(theme.palette.primary.main, 0.3), '&:hover': { borderColor: 'primary.main' } }}
          >
            Skip for now
          </Button>
        )}
      </Box>
    </motion.div>
  );
}
