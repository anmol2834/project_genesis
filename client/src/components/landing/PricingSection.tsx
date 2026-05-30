'use client';

import { Box, Typography, Button, useTheme, alpha } from '@mui/material';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import { motion } from 'framer-motion';
import NextLink from 'next/link';
import { FadeUp, StaggerContainer, fadeUp } from './motion';
import { lightGradients, darkGradients } from '@/theme/palette';

const PLANS = [
  {
    name: 'Starter',
    tagline: 'Perfect for individuals getting started.',
    highlight: false,
    features: [
      'AI-powered email automation',
      'Smart filtering & prioritization',
      'Basic analytics dashboard',
      'Email support',
    ],
  },
  {
    name: 'Professional',
    tagline: 'For professionals who live in their inbox.',
    highlight: true,
    badge: 'Most popular',
    features: [
      'Everything in Starter',
      'Advanced AI reply modes',
      'Campaign inbox merge',
      'Priority support',
      'Custom integrations',
    ],
  },
  {
    name: 'Enterprise',
    tagline: 'Unlimited scale with dedicated infrastructure.',
    highlight: false,
    features: [
      'Everything in Professional',
      'Unlimited mailboxes',
      'Dedicated infrastructure',
      'SLA guarantees',
      'Custom AI training',
      'White-label options',
    ],
  },
];

export default function PricingSection() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  return (
    <Box
      id="pricing"
      component="section"
      sx={{ py: { xs: 7, sm: 10, md: 14 }, px: { xs: 2, sm: 3, md: 4 } }}
    >
      <Box sx={{ maxWidth: 960, mx: 'auto' }}>
        <FadeUp>
          <Box sx={{ textAlign: 'center', mb: { xs: 4, sm: 5 } }}>
            <Typography variant="overline" sx={{ color: 'primary.main', mb: 0.75, display: 'block' }}>
              Simple pricing
            </Typography>
            <Typography
              variant="h2"
              sx={{ mb: 1, fontSize: { xs: 'clamp(1.4rem, 5vw, 1.75rem)', md: '2rem' } }}
            >
              Pay for what you{' '}
              <Box component="span" sx={{ background: grad.primary, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                actually use
              </Box>
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', maxWidth: 360, mx: 'auto', fontSize: '0.875rem' }}>
              No hidden fees. No setup costs. Cancel anytime.
            </Typography>
          </Box>
        </FadeUp>

        <StaggerContainer>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: 'repeat(3, 1fr)' },
              gap: { xs: 1.5, sm: 2 },
              alignItems: 'stretch',
            }}
          >
            {PLANS.map((plan) => (
              <motion.div key={plan.name} variants={fadeUp} style={{ display: 'flex' }}>
                <Box
                  sx={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    p: { xs: 2.5, sm: 3 },
                    borderRadius: '16px',
                    border: plan.highlight
                      ? `2px solid ${theme.palette.primary.main}`
                      : `1px solid ${theme.palette.divider}`,
                    background: plan.highlight
                      ? isDark
                        ? `linear-gradient(160deg, ${alpha('#818cf8', 0.10)} 0%, ${alpha('#a78bfa', 0.06)} 100%)`
                        : `linear-gradient(160deg, ${alpha('#4338ca', 0.05)} 0%, ${alpha('#7c3aed', 0.03)} 100%)`
                      : theme.palette.background.paper,
                    position: 'relative',
                    overflow: 'hidden',
                    transition: 'all 0.25s ease',
                    '&:hover': {
                      transform: 'translateY(-3px)',
                      boxShadow: plan.highlight
                        ? `0 12px 32px ${alpha(theme.palette.primary.main, isDark ? 0.20 : 0.12)}`
                        : theme.shadows[3],
                    },
                  }}
                >
                  {plan.highlight && (
                    <Box
                      sx={{
                        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
                        background: grad.primary, borderRadius: '16px 16px 0 0',
                      }}
                    />
                  )}

                  {plan.badge && (
                    <Box
                      sx={{
                        position: 'absolute', top: 14, right: 14,
                        px: 1.25, py: 0.4, borderRadius: '6px',
                        background: grad.primary,
                      }}
                    >
                      <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: '#fff', letterSpacing: '0.04em' }}>
                        {plan.badge}
                      </Typography>
                    </Box>
                  )}

                  <Typography sx={{ fontWeight: 700, fontSize: '1.25rem', color: 'text.primary', mb: 1 }}>
                    {plan.name}
                  </Typography>

                  <Typography sx={{ color: 'text.secondary', fontSize: '0.85rem', lineHeight: 1.5, mb: 3 }}>
                    {plan.tagline}
                  </Typography>

                  <Box
                    sx={{
                      mb: 3,
                      p: 2,
                      borderRadius: '10px',
                      background: isDark
                        ? alpha(theme.palette.primary.main, 0.08)
                        : alpha(theme.palette.primary.main, 0.05),
                      border: `1px dashed ${alpha(theme.palette.primary.main, isDark ? 0.3 : 0.2)}`,
                      textAlign: 'center',
                    }}
                  >
                    <Typography
                      sx={{
                        fontSize: '1.5rem',
                        fontWeight: 800,
                        mb: 0.5,
                        background: grad.primary,
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        backgroundClip: 'text',
                      }}
                    >
                      Coming Soon
                    </Typography>
                    <Typography sx={{ color: 'text.disabled', fontSize: '0.75rem' }}>
                      Pricing to be announced after launch
                    </Typography>
                  </Box>

                  <Box sx={{ height: '1px', background: theme.palette.divider, mb: 2.5 }} />

                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25, flex: 1 }}>
                    {plan.features.map((feature) => (
                      <Box key={feature} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                        <Box
                          sx={{
                            width: 18, height: 18, borderRadius: '50%', flexShrink: 0, mt: 0.15,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            background: alpha(theme.palette.success.main, isDark ? 0.18 : 0.10),
                          }}
                        >
                          <CheckRoundedIcon sx={{ fontSize: 11, color: 'success.main' }} />
                        </Box>
                        <Typography
                          sx={{
                            fontSize: '0.85rem',
                            color: 'text.primary',
                            lineHeight: 1.5,
                          }}
                        >
                          {feature}
                        </Typography>
                      </Box>
                    ))}
                  </Box>

                  <Button
                    component={NextLink}
                    href="/waitlist"
                    variant={plan.highlight ? 'contained' : 'outlined'}
                    fullWidth
                    sx={{
                      mt: 3,
                      minHeight: 42,
                      fontWeight: 600,
                      fontSize: '0.875rem',
                      py: 1,
                      ...(plan.highlight && {
                        background: grad.primary,
                        boxShadow: isDark
                          ? '0 8px 24px rgba(129,140,248,0.28)'
                          : '0 8px 24px rgba(67,56,202,0.20)',
                        '&:hover': { filter: 'brightness(1.08)', transform: 'translateY(-1px)' },
                      }),
                      ...(!plan.highlight && {
                        borderColor: alpha(theme.palette.primary.main, isDark ? 0.35 : 0.30),
                        '&:hover': { borderColor: 'primary.main' },
                      }),
                      transition: 'all 0.2s ease',
                    }}
                  >
                    Join Waitlist
                  </Button>
                </Box>
              </motion.div>
            ))}
          </Box>
        </StaggerContainer>


      </Box>
    </Box>
  );
}
