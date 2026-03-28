'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Box, Typography, CircularProgress } from '@mui/material';
import { handleOAuthCallback } from '@/utils/oauth';
import { useConnectEmail } from '@/hooks/mutations/useEmailMutations';

export default function OAuthCallbackPage() {
  const router = useRouter();
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing');
  const [errorMessage, setErrorMessage] = useState('');
  const { mutateAsync: connectEmail, isSuccess, isError, error, isPending } = useConnectEmail();
  const hasProcessed = useRef(false);

  useEffect(() => {
    // Prevent double execution in React Strict Mode
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processCallback = async () => {
      try {
        const result = handleOAuthCallback();
        
        if (!result) {
          setStatus('error');
          setErrorMessage('Invalid OAuth callback. Please try again.');
          setTimeout(() => router.push('/dashboard/accounts'), 3000);
          return;
        }

        const { code, provider, codeVerifier } = result;

        console.log('[OAuth Callback] Processing:', { provider, hasCode: !!code, hasCodeVerifier: !!codeVerifier });

        // Send authorization code to backend (include code_verifier for Outlook PKCE)
        try {
          const response = await connectEmail({
            provider,
            connection_type: 'oauth',
            credentials: codeVerifier ? { code, code_verifier: codeVerifier } : { code },
          });
          
          console.log('[OAuth Callback] Success:', response);
          setStatus('success');
          setTimeout(() => router.push('/dashboard/accounts'), 2000);
        } catch (err: any) {
          console.error('[OAuth Callback] Error:', err);
          setStatus('error');
          setErrorMessage(err?.message || 'Failed to connect email account');
          setTimeout(() => router.push('/dashboard/accounts'), 3000);
        }
      } catch (error) {
        console.error('[OAuth Callback] Processing error:', error);
        setStatus('error');
        setErrorMessage('An unexpected error occurred');
        setTimeout(() => router.push('/dashboard/accounts'), 3000);
      }
    };

    processCallback();
  }, [connectEmail, router]);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        gap: 2,
      }}
    >
      {status === 'processing' && (
        <>
          <CircularProgress size={48} />
          <Typography sx={{ fontSize: '1rem', fontWeight: 600 }}>
            Connecting your email account...
          </Typography>
        </>
      )}

      {status === 'success' && (
        <>
          <Box
            sx={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'rgba(52,211,153,0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Typography sx={{ fontSize: '2rem' }}>✓</Typography>
          </Box>
          <Typography sx={{ fontSize: '1rem', fontWeight: 600, color: '#34d399' }}>
            Email account connected successfully!
          </Typography>
          <Typography sx={{ fontSize: '0.875rem', color: 'text.secondary' }}>
            Redirecting to accounts page...
          </Typography>
        </>
      )}

      {status === 'error' && (
        <>
          <Box
            sx={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'rgba(248,113,113,0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Typography sx={{ fontSize: '2rem' }}>✕</Typography>
          </Box>
          <Typography sx={{ fontSize: '1rem', fontWeight: 600, color: '#f87171' }}>
            Connection failed
          </Typography>
          <Typography sx={{ fontSize: '0.875rem', color: 'text.secondary' }}>
            {errorMessage}
          </Typography>
          <Typography sx={{ fontSize: '0.875rem', color: 'text.secondary' }}>
            Redirecting back...
          </Typography>
        </>
      )}
    </Box>
  );
}
