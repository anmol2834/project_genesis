'use client';

import { Box, Typography, Button, useTheme, alpha } from '@mui/material';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import { motion } from 'framer-motion';
import NextLink from 'next/link';
import { FadeUp, StaggerContainer, fadeUp } from './motion';
import { lightGradients, darkGradients } from '@/theme/palette';

const PLANS = [
  {
    name: 'Free',
    price: '$0',
    period: 'forever',
    tagline: 'Get started with AI email automation.',
    cta: 'Start for free',
    ctaVariant: 'outlined' as const,
    highlight: false,
    features: [
      { text: '500 emails / month',          included: true  },
      { text: '1 connected mailbox',          included: true  },
      { text: 'AI reply drafts',              included: true  },
      { text: 'Smart filtering',              included: true  },
      { text: 'Auto-reply mode',              included: false },
      { text: 'Campaign inbox merge',         included: false },
      { text: 'Analytics dashboard',          included: false },
      { text: 'Priority support',             included: false },
    ],
  },
  {
    name: 'Pro',
    price: '$29',
    period: 'per month',
    tagline: 'For professionals who live in their inbox.',
    cta: 'Start 14-day trial',
    ctaVariant: 'contained' as const,
    highlight: true,
    badge: 'Most popular',
    features: [
      { text: '25,000 emails / month',        included: true  },
      { text: '5 connected mailboxes',        included: true  },
      { text: 'AI reply drafts',              included: true  },
      { text: 'Smart filtering',              included: true  },
      { text: 'Auto-reply mode',              included: true  },
      { text: 'Campaign inbox merge',         included: true  },
      { text: 'Analytics dashboard',          included: true  },
      { text: 'Priority support',             included: false },
    ],
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    period: 'contact us',
    tagline: 'Unlimited scale with dedicated infrastructure.',
    cta: 'Book a demo',
    ctaVariant: 'outlined' as const,
    highlight: false,
    features: [
      { text: 'Unlimited emails',             included: true  },
      { text: 'Unlimited mailboxes',          included: true  },
      { text: 'AI reply drafts',              included: true  },
      { text: 'Smart filtering',              included: true  },
      { text: 'Auto-reply mode',              included: true  },
      { text: 'Campaign inbox merge',         included: true  },
      { text: 'Analytics dashboard',          included: true  },
      { text: 'Priority support',             included: true  },
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
                    p: { xs: 2.5, sm: 2.75 },
                    borderRadius: '14px',
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
                  {/* Highlight glow */}
                  {plan.highlight && (
                    <Box
                      sx={{
                        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
                        background: grad.primary, borderRadius: '14px 14px 0 0',
                      }}
                    />
                  )}

                  {/* Badge */}
                  {plan.badge && (
                    <Box
                      sx={{
                        position: 'absolute', top: 12, right: 12,
                        px: 1, py: 0.25, borderRadius: '5px',
                        background: grad.primary,
                      }}
                    >
                      <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: '#fff', letterSpacing: '0.04em' }}>
                        {plan.badge}
                      </Typography>
                    </Box>
                  )}

                  {/* Plan name */}
                  <Typography sx={{ fontWeight: 600, fontSize: '0.7rem', color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.08em', mb: 1.25 }}>
                    {plan.name}
                  </Typography>

                  {/* Price */}
                  <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5, mb: 0.4 }}>
                    <Typography
                      sx={{
                        fontSize: '1.75rem',
                        fontWeight: 700,
                        lineHeight: 1,
                        background: plan.highlight ? grad.primary : 'none',
                        WebkitBackgroundClip: plan.highlight ? 'text' : 'unset',
                        WebkitTextFillColor: plan.highlight ? 'transparent' : 'unset',
                        backgroundClip: plan.highlight ? 'text' : 'unset',
                        color: plan.highlight ? 'unset' : 'text.primary',
                      }}
                    >
                      {plan.price}
                    </Typography>
                    <Typography sx={{ color: 'text.disabled', fontSize: '0.75rem' }}>
                      {plan.period}
                    </Typography>
                  </Box>

                  <Typography sx={{ color: 'text.secondary', fontSize: '0.8rem', lineHeight: 1.5, mb: 2 }}>
                    {plan.tagline}
                  </Typography>

                  {/* CTA */}
                  <Button
                    component={NextLink}
                    href="/sign-in"
                    variant={plan.ctaVariant}
                    fullWidth
                    startIcon={plan.highlight ? <BoltRoundedIcon sx={{ fontSize: '14px !important' }} /> : undefined}
                    sx={{
                      mb: 2,
                      minHeight: 36,
                      fontWeight: 600,
                      fontSize: '0.8rem',
                      py: 0.75,
                      ...(plan.ctaVariant === 'contained' && {
                        background: grad.primary,
                        boxShadow: isDark
                          ? '0 8px 24px rgba(129,140,248,0.28)'
                          : '0 8px 24px rgba(67,56,202,0.20)',
                        '&:hover': { filter: 'brightness(1.08)', transform: 'translateY(-1px)' },
                      }),
                      ...(plan.ctaVariant === 'outlined' && {
                        borderColor: alpha(theme.palette.primary.main, isDark ? 0.35 : 0.30),
                        '&:hover': { borderColor: 'primary.main' },
                      }),
                      transition: 'all 0.2s ease',
                    }}
                  >
                    {plan.cta}
                  </Button>

                  {/* Divider */}
                  <Box sx={{ height: '1px', background: theme.palette.divider, mb: 2 }} />

                  {/* Feature list */}
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, flex: 1 }}>
                    {plan.features.map((f) => (
                      <Box key={f.text} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box
                          sx={{
                            width: 16, height: 16, borderRadius: '50%', flexShrink: 0,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            background: f.included
                              ? alpha(theme.palette.success.main, isDark ? 0.18 : 0.10)
                              : alpha(theme.palette.text.disabled, isDark ? 0.12 : 0.08),
                          }}
                        >
                          {f.included
                            ? <CheckRoundedIcon sx={{ fontSize: 10, color: 'success.main' }} />
                            : <CloseRoundedIcon sx={{ fontSize: 10, color: 'text.disabled' }} />
                          }
                        </Box>
                        <Typography
                          sx={{
                            fontSize: '0.8rem',
                            color: f.included ? 'text.primary' : 'text.disabled',
                          }}
                        >
                          {f.text}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                </Box>
              </motion.div>
            ))}
          </Box>
        </StaggerContainer>


      </Box>
    </Box>
  );
}
