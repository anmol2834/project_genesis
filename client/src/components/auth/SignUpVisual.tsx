'use client';

import { useEffect, useState, useRef } from 'react';
import { Box, Typography, useTheme, alpha, GlobalStyles } from '@mui/material';
import PersonRoundedIcon from '@mui/icons-material/PersonRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import BusinessRoundedIcon from '@mui/icons-material/BusinessRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import InboxRoundedIcon from '@mui/icons-material/InboxRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import SecurityRoundedIcon from '@mui/icons-material/SecurityRounded';
import { lightGradients, darkGradients } from '@/theme/palette';

interface Props { currentStep: number; }

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

// ── Keyframes injected once globally — never restart on re-render ───────────
const GLOBAL_KEYFRAMES = (
  <GlobalStyles styles={{
    '@keyframes suv-breathe': {
      '0%,100%': { transform: 'scale(1)',    opacity: 0.5  },
      '50%':     { transform: 'scale(1.08)', opacity: 0.72 },
    },
    '@keyframes suv-breathe2': {
      '0%,100%': { transform: 'scale(1)',    opacity: 0.32 },
      '50%':     { transform: 'scale(1.1)',  opacity: 0.58 },
    },
    '@keyframes suv-gridpulse': {
      '0%,100%': { opacity: 0.28 },
      '50%':     { opacity: 0.52 },
    },
    '@keyframes suv-spin': {
      from: { transform: 'rotate(0deg)'   },
      to:   { transform: 'rotate(360deg)' },
    },
    '@keyframes suv-pulse': {
      '0%,100%': { transform: 'scale(1)',   opacity: 0.45 },
      '50%':     { transform: 'scale(2.4)', opacity: 0    },
    },
  }} />
);

const STEP_CONFIGS = {
  1: {
    title: 'Create Account',
    subtitle: 'Join thousands of professionals',
    icon: PersonRoundedIcon,
    color: '#6366f1',
    tagline: 'Enterprise-grade security from the start',
    features: [
      { icon: SecurityRoundedIcon,    text: 'Enterprise-grade security', color: '#10b981' },
      { icon: BoltRoundedIcon,        text: 'Lightning-fast setup',      color: '#f59e0b' },
      { icon: AutoAwesomeRoundedIcon, text: 'AI-powered from day one',   color: '#8b5cf6' },
    ],
  },
  2: {
    title: 'Verify Email',
    subtitle: 'Secure your account',
    icon: EmailRoundedIcon,
    color: '#8b5cf6',
    tagline: 'One-time code sent to your inbox',
    features: [
      { icon: SecurityRoundedIcon,    text: 'Email verification sent',   color: '#10b981' },
      { icon: CheckCircleRoundedIcon, text: 'Account protection active', color: '#06b6d4' },
      { icon: BoltRoundedIcon,        text: 'Almost ready to go',        color: '#f59e0b' },
    ],
  },
  3: {
    title: 'Business Setup',
    subtitle: 'Tell us about your company',
    icon: BusinessRoundedIcon,
    color: '#06b6d4',
    tagline: 'AI learns your business context instantly',
    features: [
      { icon: BusinessRoundedIcon,    text: 'Business context learning', color: '#6366f1' },
      { icon: AutoAwesomeRoundedIcon, text: 'AI personalization begins', color: '#8b5cf6' },
      { icon: CheckCircleRoundedIcon, text: 'Smart industry insights',   color: '#10b981' },
    ],
  },
  4: {
    title: 'AI Training',
    subtitle: 'Customize your AI assistant',
    icon: AutoAwesomeRoundedIcon,
    color: '#8b5cf6',
    tagline: 'Your tone, your style — AI adapts',
    features: [
      { icon: AutoAwesomeRoundedIcon, text: 'Learning your tone',   color: '#8b5cf6' },
      { icon: BoltRoundedIcon,        text: 'Processing use cases', color: '#f59e0b' },
      { icon: CheckCircleRoundedIcon, text: 'AI model calibrating', color: '#10b981' },
    ],
  },
  5: {
    title: 'Connect Inbox',
    subtitle: 'Link your email accounts',
    icon: InboxRoundedIcon,
    color: '#10b981',
    tagline: 'Real-time sync, zero latency',
    features: [
      { icon: InboxRoundedIcon,    text: 'Real-time email sync',    color: '#06b6d4' },
      { icon: BoltRoundedIcon,     text: 'Instant AI replies',      color: '#f59e0b' },
      { icon: SecurityRoundedIcon, text: 'Secure OAuth connection', color: '#10b981' },
    ],
  },
  6: {
    title: 'Ready to Launch',
    subtitle: 'Your AI is initialized',
    icon: CheckCircleRoundedIcon,
    color: '#10b981',
    tagline: "Everything is set — let's automate",
    features: [
      { icon: CheckCircleRoundedIcon, text: 'Setup complete',       color: '#10b981' },
      { icon: AutoAwesomeRoundedIcon, text: 'AI ready to work',     color: '#8b5cf6' },
      { icon: BoltRoundedIcon,        text: 'Start automating now', color: '#f59e0b' },
    ],
  },
} as const;

export default function SignUpVisual({ currentStep }: Props) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  // ── Feature cycling ─────────────────────────────────────────────────────
  // Keep a stable featureIdx that doesn't jump on step change.
  // We fade everything out first (via `transitioning`), then swap content,
  // then fade back in — so there's never a raw instant jump.
  const cancelRef = useRef(false);
  const [featureIdx, setFeatureIdx]       = useState(0);
  const [transitioning, setTransitioning] = useState(false); // true = all features dimmed

  const config   = STEP_CONFIGS[currentStep as keyof typeof STEP_CONFIGS] ?? STEP_CONFIGS[1];
  const StepIcon = config.icon;
  const pct      = Math.round((currentStep / 6) * 100);

  useEffect(() => {
    cancelRef.current = false;

    // 1. Dim everything smoothly before resetting index
    setTransitioning(true);

    const init = setTimeout(() => {
      setFeatureIdx(0);
      setTransitioning(false);

      // 2. Start cycling after the fade-in settles
      const cycle = async () => {
        await sleep(2500); // first dwell
        let i = 1;
        while (!cancelRef.current) {
          if (cancelRef.current) return;
          setFeatureIdx(i % config.features.length);
          await sleep(2500);
          i++;
        }
      };
      cycle();
    }, 400); // matches the CSS opacity transition duration

    return () => {
      cancelRef.current = true;
      clearTimeout(init);
    };
  }, [currentStep, config.features.length]);

  return (
    <>
      {GLOBAL_KEYFRAMES}

      <Box
        sx={{
          width: '100%', height: '100%',
          display: 'flex', flexDirection: 'column',
          justifyContent: 'center', alignItems: 'center',
          px: 4, py: 5,
          position: 'relative', overflow: 'hidden',
          background: isDark
            ? 'linear-gradient(160deg, #0f172a 0%, #1a1040 50%, #0f172a 100%)'
            : 'linear-gradient(160deg, #eef2ff 0%, #f5f3ff 50%, #ede9fe 100%)',
        }}
      >
        {/* ── Dot grid — animation name is stable, never restarts ──────── */}
        <Box sx={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          backgroundImage: isDark
            ? `radial-gradient(${alpha('#818cf8', 0.08)} 1px, transparent 1px)`
            : `radial-gradient(${alpha('#4338ca', 0.05)} 1px, transparent 1px)`,
          backgroundSize: '28px 28px',
          animation: 'suv-gridpulse 9s ease-in-out infinite',
        }} />

        {/* ── Primary orb — color via CSS var so animation never restarts ─ */}
        {/* We separate the animated wrapper from the color-changing inner div */}
        <Box sx={{
          position: 'absolute', top: '-18%', right: '-12%',
          width: '60%', height: '60%',
          animation: 'suv-breathe 12s ease-in-out infinite',
          pointerEvents: 'none',
        }}>
          <Box sx={{
            width: '100%', height: '100%', borderRadius: '50%',
            background: isDark
              ? `radial-gradient(ellipse, ${alpha(config.color, 0.16)} 0%, transparent 68%)`
              : `radial-gradient(ellipse, ${alpha(config.color, 0.11)} 0%, transparent 68%)`,
            transition: 'background 1s ease',
          }} />
        </Box>

        {/* ── Secondary orb ────────────────────────────────────────────── */}
        <Box sx={{
          position: 'absolute', bottom: '-18%', left: '-12%',
          width: '55%', height: '55%',
          animation: 'suv-breathe2 15s ease-in-out infinite',
          animationDelay: '4s',
          pointerEvents: 'none',
        }}>
          <Box sx={{
            width: '100%', height: '100%', borderRadius: '50%',
            background: isDark
              ? 'radial-gradient(ellipse, rgba(167,139,250,0.12) 0%, transparent 68%)'
              : 'radial-gradient(ellipse, rgba(124,58,237,0.07) 0%, transparent 68%)',
          }} />
        </Box>

        {/* ── Brand mark ───────────────────────────────────────────────── */}
        <Box sx={{ position: 'relative', zIndex: 1, mb: 3.5, textAlign: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'center', mb: 0.75 }}>
            <Box sx={{
              width: 32, height: 32, borderRadius: '9px',
              background: grad.primary,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <BoltRoundedIcon sx={{ color: '#fff', fontSize: 17 }} />
            </Box>
            <Typography sx={{ fontWeight: 700, fontSize: '1.05rem', letterSpacing: '-0.02em', color: 'text.primary' }}>
              MailFlow<Box component="span" sx={{ color: 'primary.main' }}>AI</Box>
            </Typography>
          </Box>
          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', maxWidth: 220, mx: 'auto', lineHeight: 1.5 }}>
            Setting up your AI email assistant
          </Typography>
        </Box>

        {/* ── Step card ────────────────────────────────────────────────── */}
        <Box sx={{ width: '100%', maxWidth: 310, mb: 2.5, position: 'relative', zIndex: 1 }}>
          <Box sx={{
            p: 2.5, borderRadius: '14px',
            border: `1px solid ${theme.palette.divider}`,
            background: isDark
              ? alpha(theme.palette.background.paper, 0.85)
              : alpha(theme.palette.background.paper, 0.92),
            backdropFilter: 'blur(8px)',
            boxShadow: isDark
              ? '0 8px 32px rgba(0,0,0,0.35)'
              : '0 8px 32px rgba(67,56,202,0.09)',
          }}>

            {/* Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
              {/* Icon box — color transitions, animation wrapper is separate */}
              <Box sx={{
                width: 40, height: 40, borderRadius: '10px', flexShrink: 0,
                background: alpha(config.color, isDark ? 0.18 : 0.10),
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 0.8s ease',
              }}>
                <StepIcon sx={{ fontSize: 20, color: config.color, transition: 'color 0.8s ease' }} />
              </Box>

              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ fontSize: '0.88rem', fontWeight: 700, color: 'text.primary', lineHeight: 1.2 }}>
                  {config.title}
                </Typography>
                <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', lineHeight: 1.3, mt: 0.2 }}>
                  {config.subtitle}
                </Typography>
              </Box>

              {/* Pulse dot — animation wrapper separate from color div */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6, flexShrink: 0 }}>
                <Box sx={{ position: 'relative', width: 8, height: 8 }}>
                  {/* Animated ring — no color prop, so animation never restarts */}
                  <Box sx={{
                    position: 'absolute', inset: 0, borderRadius: '50%',
                    background: config.color,
                    animation: 'suv-pulse 3.5s ease-in-out infinite',
                    transition: 'background 0.8s ease',
                  }} />
                  {/* Static center dot */}
                  <Box sx={{
                    position: 'absolute', inset: '1.5px', borderRadius: '50%',
                    background: config.color,
                    transition: 'background 0.8s ease',
                  }} />
                </Box>
                <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', fontWeight: 600 }}>
                  {currentStep}/6
                </Typography>
              </Box>
            </Box>

            {/* Progress bar */}
            <Box sx={{ mb: 2 }}>
              <Box sx={{
                width: '100%', height: 5, borderRadius: 3,
                background: alpha(theme.palette.text.disabled, 0.08),
                overflow: 'hidden',
              }}>
                <Box sx={{
                  height: '100%', borderRadius: 3,
                  background: `linear-gradient(90deg, ${config.color}, ${alpha(config.color, 0.75)})`,
                  width: `${pct}%`,
                  transition: 'width 1s cubic-bezier(0.22,1,0.36,1), background 0.8s ease',
                }} />
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
                <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>
                  Step {currentStep} of 6
                </Typography>
                <Typography sx={{ fontSize: '0.62rem', color: config.color, fontWeight: 600, transition: 'color 0.8s ease' }}>
                  {pct}%
                </Typography>
              </Box>
            </Box>

            {/* Feature rows */}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.85 }}>
              {config.features.map((feature, i) => {
                const FeatureIcon = feature.icon;
                // When transitioning between steps, dim all rows equally
                const isActive = !transitioning && i === featureIdx;
                const opacity  = transitioning ? 0.35 : isActive ? 1 : 0.35;

                return (
                  <Box
                    key={feature.text}
                    sx={{
                      display: 'flex', alignItems: 'center', gap: 1,
                      opacity,
                      transition: 'opacity 0.4s ease',
                    }}
                  >
                    <Box sx={{
                      width: 22, height: 22, borderRadius: '6px', flexShrink: 0,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      background: isActive
                        ? alpha(feature.color, isDark ? 0.22 : 0.12)
                        : alpha(theme.palette.text.disabled, 0.06),
                      transition: 'background 0.4s ease',
                    }}>
                      <FeatureIcon sx={{
                        fontSize: 12,
                        color: isActive ? feature.color : theme.palette.text.disabled,
                        transition: 'color 0.4s ease',
                      }} />
                    </Box>
                    <Typography sx={{
                      flex: 1, fontSize: '0.72rem',
                      color: isActive ? 'text.primary' : 'text.disabled',
                      fontWeight: isActive ? 600 : 400,
                      transition: 'color 0.4s ease, font-weight 0.4s ease',
                    }}>
                      {feature.text}
                    </Typography>
                    <Box sx={{
                      width: 5, height: 5, borderRadius: '50%',
                      background: feature.color,
                      opacity: isActive ? 1 : 0,
                      transition: 'opacity 0.4s ease',
                      flexShrink: 0,
                    }} />
                  </Box>
                );
              })}
            </Box>

            {/* Tagline */}
            <Box sx={{
              mt: 1.75, pt: 1.5,
              borderTop: `1px solid ${alpha(theme.palette.divider, 0.6)}`,
              display: 'flex', alignItems: 'center', gap: 0.75,
            }}>
              {/* Spin wrapper is stable — color change on inner element only */}
              <Box sx={{
                flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                animation: 'suv-spin 18s linear infinite',
              }}>
                <AutoAwesomeRoundedIcon sx={{
                  fontSize: 12, color: config.color,
                  transition: 'color 0.8s ease',
                }} />
              </Box>
              <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', lineHeight: 1.4 }}>
                {config.tagline}
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* ── Step pills ───────────────────────────────────────────────── */}
        <Box sx={{ position: 'relative', zIndex: 1, width: '100%', maxWidth: 310 }}>
          <Typography sx={{
            fontSize: '0.6rem', fontWeight: 600, color: 'text.disabled',
            textTransform: 'uppercase', letterSpacing: '0.08em',
            mb: 1, textAlign: 'center',
          }}>
            Setup Progress
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
            {Array.from({ length: 6 }, (_, i) => {
              const n      = i + 1;
              const active = n === currentStep;
              const done   = n < currentStep;
              return (
                <Box
                  key={n}
                  sx={{
                    height: 6, borderRadius: '3px',
                    width: active ? 26 : 6,
                    background: done
                      ? '#10b981'
                      : active
                        ? config.color
                        : alpha(theme.palette.text.disabled, 0.2),
                    transition: 'width 0.6s cubic-bezier(0.22,1,0.36,1), background 0.6s ease',
                  }}
                />
              );
            })}
          </Box>
        </Box>
      </Box>
    </>
  );
}
