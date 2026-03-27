'use client';

import { useState, useCallback, useId } from 'react';
import {
  Box, Typography, Button, TextField, IconButton, InputAdornment,
  Divider, Checkbox, FormControlLabel, Alert, CircularProgress,
  useTheme, alpha,
} from '@mui/material';
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded';
import VisibilityOffRoundedIcon from '@mui/icons-material/VisibilityOffRounded';
import { motion, AnimatePresence } from 'framer-motion';
import NextLink from 'next/link';
import { useRouter } from 'next/navigation';
import { lightGradients, darkGradients } from '@/theme/palette';
import { useAuth } from '@/contexts/AuthContext';
import { useLogin, useGetProfile } from '@/hooks/mutations/useAuthMutations';

// ─── Google SVG icon (no external dep) ───────────────────────────────────────
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

// ─── Microsoft SVG icon ───────────────────────────────────────────────────────
function MicrosoftIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect x="1"  y="1"  width="10.5" height="10.5" fill="#F25022"/>
      <rect x="12.5" y="1"  width="10.5" height="10.5" fill="#7FBA00"/>
      <rect x="1"  y="12.5" width="10.5" height="10.5" fill="#00A4EF"/>
      <rect x="12.5" y="12.5" width="10.5" height="10.5" fill="#FFB900"/>
    </svg>
  );
}

type AuthState = 'idle' | 'loading' | 'success' | 'error';

interface FormState {
  email: string;
  password: string;
  remember: boolean;
}

export default function SignInForm() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const emailId = useId();
  const passwordId = useId();
  const router = useRouter();
  
  // Auth context and mutations
  const { setAuthData } = useAuth();
  const loginMutation = useLogin();
  const getProfileMutation = useGetProfile();

  const [form, setForm] = useState<FormState>({ email: '', password: '', remember: false });
  const [showPassword, setShowPassword] = useState(false);
  const [oauthLoading, setOauthLoading] = useState<'google' | 'microsoft' | null>(null);
  const [touched, setTouched] = useState({ email: false, password: false });

  // Inline validation
  const emailError = touched.email && form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)
    ? 'Enter a valid email address'
    : '';
  const passwordError = touched.password && form.password && form.password.length < 6
    ? 'Password must be at least 6 characters'
    : '';
  
  const isLoading = loginMutation.isPending || getProfileMutation.isPending;
  const canSubmit = form.email && form.password && !emailError && !passwordError && !isLoading;

  const handleChange = useCallback((field: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = field === 'remember' ? e.target.checked : e.target.value;
    setForm((p) => ({ ...p, [field]: value }));
    
    // Clear errors when user starts typing
    if (loginMutation.isError) {
      loginMutation.reset();
    }
  }, [loginMutation]);

  const handleBlur = useCallback((field: 'email' | 'password') => () => {
    setTouched((p) => ({ ...p, [field]: true }));
  }, []);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched({ email: true, password: true });
    if (!canSubmit) return;

    try {
      // Step 1: Login and get tokens
      const loginResponse = await loginMutation.mutateAsync({
        email: form.email,
        password: form.password,
      });

      // Step 2: Fetch full user profile
      const userProfile = await getProfileMutation.mutateAsync(loginResponse.tokens.access_token);

      // Step 3: Update auth context with user data and tokens
      setAuthData(userProfile, loginResponse.tokens);

      // Step 4: Redirect to dashboard
      router.push('/dashboard');
    } catch (error) {
      // Error is already handled by React Query and displayed via loginMutation.error
      console.error('[SignInForm] Login failed:', error);
    }
  }, [canSubmit, form.email, form.password, loginMutation, getProfileMutation, setAuthData, router]);

  const handleOAuth = useCallback(async (provider: 'google' | 'microsoft') => {
    setOauthLoading(provider);
    // TODO: Implement OAuth flow
    await new Promise((r) => setTimeout(r, 1200));
    setOauthLoading(null);
  }, []);

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      fontSize: '0.875rem',
      borderRadius: '8px',
      transition: 'box-shadow 0.2s ease',
      '&.Mui-focused': {
        boxShadow: `0 0 0 3px ${alpha(theme.palette.primary.main, isDark ? 0.18 : 0.12)}`,
      },
    },
    '& .MuiInputLabel-root': { fontSize: '0.875rem' },
    '& .MuiFormHelperText-root': { fontSize: '0.72rem', mx: 0, mt: 0.5 },
  };

  // Get error message from either mutation
  const errorMsg = loginMutation.error?.message || getProfileMutation.error?.message || '';

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: 'easeOut' }}
      style={{ width: '100%' }}
    >
      <Box sx={{ width: '100%', maxWidth: 380, mx: 'auto' }}>

        {/* Header */}
        <Box sx={{ mb: 3, textAlign: 'center' }}>
          <Typography
            variant="h5"
            sx={{ fontWeight: 700, fontSize: { xs: '1.2rem', sm: '1.35rem' }, letterSpacing: '-0.02em', mb: 0.5 }}
          >
            Welcome back
          </Typography>
          <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary', lineHeight: 1.5 }}>
            Sign in to your MailFlowAI account
          </Typography>
        </Box>

        {/* Error alert */}
        <AnimatePresence>
          {errorMsg && (
            <motion.div
              initial={{ opacity: 0, height: 0, marginBottom: 0 }}
              animate={{ opacity: 1, height: 'auto', marginBottom: 14 }}
              exit={{ opacity: 0, height: 0, marginBottom: 0 }}
              transition={{ duration: 0.25 }}
            >
              <Alert
                severity="error"
                onClose={() => {
                  loginMutation.reset();
                  getProfileMutation.reset();
                }}
                sx={{ fontSize: '0.78rem', py: 0.5, borderRadius: '8px', '& .MuiAlert-icon': { fontSize: 16 } }}
              >
                {errorMsg}
              </Alert>
            </motion.div>
          )}
        </AnimatePresence>

        {/* OAuth buttons */}
        <Box sx={{ display: 'flex', gap: 1, mb: 2.5 }}>
          {([
            { key: 'google',    label: 'Google',    Icon: GoogleIcon    },
            { key: 'microsoft', label: 'Microsoft', Icon: MicrosoftIcon },
          ] as const).map(({ key, label, Icon }) => (
            <Button
              key={key}
              variant="outlined"
              fullWidth
              disabled={!!oauthLoading || isLoading}
              onClick={() => handleOAuth(key)}
              startIcon={
                oauthLoading === key
                  ? <CircularProgress size={14} color="inherit" />
                  : <Icon />
              }
              sx={{
                minHeight: 38,
                fontSize: '0.8rem',
                fontWeight: 500,
                borderRadius: '8px',
                borderColor: theme.palette.divider,
                color: 'text.primary',
                gap: 0.75,
                transition: 'all 0.18s ease',
                '&:hover': {
                  borderColor: theme.palette.primary.main,
                  background: alpha(theme.palette.primary.main, isDark ? 0.06 : 0.04),
                },
                '&:disabled': { opacity: 0.55 },
              }}
            >
              {oauthLoading === key ? 'Connecting…' : `Continue with ${label}`}
            </Button>
          ))}
        </Box>

        {/* Divider */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2.5 }}>
          <Divider sx={{ flex: 1 }} />
          <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled', whiteSpace: 'nowrap' }}>
            or sign in with email
          </Typography>
          <Divider sx={{ flex: 1 }} />
        </Box>

        {/* Email + Password form */}
        <Box component="form" onSubmit={handleSubmit} noValidate sx={{ display: 'flex', flexDirection: 'column', gap: 1.75 }}>
          <TextField
            id={emailId}
            label="Email address"
            type="email"
            autoComplete="email"
            value={form.email}
            onChange={handleChange('email')}
            onBlur={handleBlur('email')}
            error={!!emailError}
            helperText={emailError}
            size="small"
            fullWidth
            sx={inputSx}
            inputProps={{ 'aria-label': 'Email address' }}
          />

          <TextField
            id={passwordId}
            label="Password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="current-password"
            value={form.password}
            onChange={handleChange('password')}
            onBlur={handleBlur('password')}
            error={!!passwordError}
            helperText={passwordError}
            size="small"
            fullWidth
            sx={inputSx}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowPassword((p) => !p)}
                    edge="end"
                    size="small"
                    tabIndex={-1}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    sx={{ color: 'text.disabled', '&:hover': { color: 'text.secondary' }, mr: -0.5 }}
                  >
                    {showPassword
                      ? <VisibilityOffRoundedIcon sx={{ fontSize: 16 }} />
                      : <VisibilityRoundedIcon sx={{ fontSize: 16 }} />
                    }
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />

          {/* Remember me + Forgot password */}
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: -0.5 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={form.remember}
                  onChange={handleChange('remember')}
                  size="small"
                  sx={{ p: 0.5, '& .MuiSvgIcon-root': { fontSize: 16 } }}
                />
              }
              label={
                <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
                  Remember me
                </Typography>
              }
              sx={{ m: 0, gap: 0.25 }}
            />
            <Box
              component={NextLink}
              href="#"
              sx={{ fontSize: '0.78rem', color: 'primary.main', fontWeight: 500, textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
            >
              Forgot password?
            </Box>
          </Box>

          {/* Submit button */}
          <Button
            type="submit"
            variant="contained"
            fullWidth
            disabled={!canSubmit}
            sx={{
              mt: 0.25,
              minHeight: 40,
              fontSize: '0.875rem',
              fontWeight: 600,
              borderRadius: '8px',
              background: canSubmit ? grad.primary : undefined,
              boxShadow: canSubmit
                ? isDark ? '0 4px 16px rgba(129,140,248,0.25)' : '0 4px 16px rgba(67,56,202,0.18)'
                : 'none',
              transition: 'all 0.2s ease',
              '&:hover': { filter: 'brightness(1.07)', transform: 'translateY(-1px)' },
              '&:active': { transform: 'translateY(0)' },
              '&:disabled': { opacity: 0.5 },
            }}
          >
            {isLoading
              ? <CircularProgress size={16} color="inherit" />
              : 'Sign in'
            }
          </Button>
        </Box>

        <Typography sx={{ textAlign: 'center', fontSize: '0.8rem', color: 'text.secondary', mt: 2.5 }}>
          Don't have an account?{' '}
          <Box
            component={NextLink}
            href="/sign-up"
            sx={{ color: 'primary.main', fontWeight: 600, textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
          >
            Start for free
          </Box>
        </Typography>

        {/* Footer links */}
        <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2, mt: 1.5 }}>
          {['Privacy Policy', 'Terms of Service', 'Security'].map((item) => (
            <Box
              key={item}
              component={NextLink}
              href="#"
              sx={{ fontSize: '0.68rem', color: 'text.disabled', textDecoration: 'none', '&:hover': { color: 'text.secondary' } }}
            >
              {item}
            </Box>
          ))}
        </Box>
      </Box>
    </motion.div>
  );
}
