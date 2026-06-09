'use client';

import { Box, Typography, Button, useTheme, alpha, Theme } from '@mui/material';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import RemoveRoundedIcon from '@mui/icons-material/RemoveRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import LockRoundedIcon from '@mui/icons-material/LockRounded';
import AllInclusiveRoundedIcon from '@mui/icons-material/AllInclusiveRounded';
import MailRoundedIcon from '@mui/icons-material/MailRounded';
import { motion } from 'framer-motion';
import NextLink from 'next/link';
import { FadeUp, StaggerContainer, fadeUp } from './motion';
import { lightGradients, darkGradients } from '@/theme/palette';

type FeatureValue = boolean | string | null;

interface Feature {
  label: string;
  starter: FeatureValue;
  pro: FeatureValue;
  growth: FeatureValue;
  enterprise: FeatureValue;
  highlight?: boolean;
}

export const FEATURES: Feature[] = [
  // Core credits & sending
  { label: 'Email processing credits/month', starter: '50 credits',  pro: '500 credits',    growth: '1,000 credits', enterprise: 'Custom',   highlight: true },
  { label: 'Email accounts',                 starter: '1 account',   pro: '3 accounts',     growth: '5 accounts',    enterprise: 'Custom' },
  { label: 'Leads / contacts',               starter: '100 leads',   pro: '2,000 leads',    growth: '3,000 leads',   enterprise: 'Custom' },
  { label: 'Active campaigns',               starter: '1 campaign',  pro: '10 campaigns',   growth: '15 campaigns',  enterprise: 'Custom' },
  // AI features
  { label: 'AI reply generation',            starter: true,          pro: true,             growth: true,            enterprise: true },
  { label: 'Zero-UI auto reply mode',        starter: true,          pro: true,             growth: true,            enterprise: true },
  { label: 'Context memory + tone adapt.',   starter: false,         pro: true,             growth: true,            enterprise: true },
  // Inbox & Automation
  { label: 'Unified inbox',                  starter: true,          pro: true,             growth: true,            enterprise: true },
  { label: 'Campaign + inbox merge',         starter: false,         pro: true,             growth: true,            enterprise: true },
  // Analytics & Research
  { label: 'Basic analytics dashboard',      starter: true,          pro: true,             growth: true,            enterprise: true },
  { label: 'AI research assistant',          starter: false,         pro: true,             growth: true,            enterprise: true },
  // Data & Integrations
  { label: 'CSV lead import',                starter: true,          pro: true,             growth: true,            enterprise: true },
  { label: 'CRM & third-party integrations', starter: false,         pro: true,             growth: true,            enterprise: true },
  { label: 'My Data vault',                  starter: false,         pro: true,             growth: true,            enterprise: true },
  // Team & Security
  { label: 'Team members',                   starter: '1 member',    pro: '5 members',      growth: '10 members',    enterprise: 'Custom' },
  { label: 'AES-256 token encryption',       starter: true,          pro: true,             growth: true,            enterprise: true },
  // Support
  { label: 'Support',                        starter: 'Email',       pro: 'Priority email', growth: 'Priority + chat', enterprise: 'Dedicated CSM' },
];

export const PLANS = [
  {
    id: 'starter',
    name: 'Starter',
    tagline: 'Try the full AI experience, free.',
    price: null,
    priceLabel: 'Free',
    priceSub: 'No credit card required',
    highlight: false,
    badge: null,
    color: '#34d399',
    ctaLabel: 'Start for free',
    ctaHref: '/sign-up',
    ctaVariant: 'outlined' as const,
    creditLabel: '50 email credits included',
    topFeatures: [
      { icon: MailRoundedIcon, text: '50 email processing credits' },
      { icon: BoltRoundedIcon, text: 'AI reply generation included' },
    ],
    bullets: [
      '1 email account',
      'Basic analytics dashboard',
      'CSV lead import',
    ],
  },
  {
    id: 'pro',
    name: 'Professional',
    tagline: 'Full AI power for growing teams.',
    price: 29,
    priceLabel: '$29',
    priceSub: 'per month · billed monthly',
    highlight: true,
    badge: 'Most Popular',
    color: '#818cf8',
    ctaLabel: 'Get started',
    ctaHref: '/sign-up',
    ctaVariant: 'contained' as const,
    creditLabel: '500 email credits / month',
    topFeatures: [
      { icon: MailRoundedIcon, text: '500 email processing credits/mo' },
      { icon: BoltRoundedIcon, text: 'Predictive AI + auto reply mode' },
    ],
    bullets: [
      '3 email accounts · 2,000 leads',
      'Context memory + tone adaptation',
      'Campaigns, CRM integrations',
      'My Data vault',
      'AI research assistant',
      'Team (up to 5 members)',
      'Priority email support',
    ],
  },
  {
    id: 'growth',
    name: 'Growth',
    tagline: 'More scale, same great AI workflow.',
    price: 39,
    priceLabel: '$39',
    priceSub: 'per month · billed monthly',
    highlight: false,
    badge: 'Best Value',
    color: '#f59e0b',
    ctaLabel: 'Get started',
    ctaHref: '/sign-up',
    ctaVariant: 'outlined' as const,
    creditLabel: '1,000 email credits / month',
    topFeatures: [
      { icon: MailRoundedIcon, text: '1,000 email processing credits/mo' },
      { icon: BoltRoundedIcon, text: 'Predictive AI + auto reply mode' },
    ],
    bullets: [
      '5 email accounts · 3,000 leads',
      '15 active campaigns',
      'Context memory + tone adaptation',
      'Campaigns, CRM integrations',
      'My Data vault',
      'AI research assistant',
      'Team (up to 10 members)',
      'Priority email + chat support',
    ],
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    tagline: 'Custom scale, dedicated infrastructure.',
    price: null,
    priceLabel: 'Custom',
    priceSub: 'contact us for pricing',
    highlight: false,
    badge: null,
    color: '#c084fc',
    ctaLabel: 'Contact us',
    ctaHref: 'mailto:hello@proxipilot.com',
    ctaVariant: 'outlined' as const,
    creditLabel: 'Custom email credits',
    topFeatures: [
      { icon: AllInclusiveRoundedIcon, text: 'Custom volume — everything scaled' },
      { icon: LockRoundedIcon,         text: 'Dedicated customer success manager' },
    ],
    bullets: [
      'Custom accounts, leads & team',
      'Custom AI training + RBAC',
      'Compliance logs + audit trail',
      'White-label + dedicated CSM',
    ],
  },
] as const;

function FeatureCell({ value, color, isDark }: { value: FeatureValue; color: string; isDark: boolean }) {
  if (value === false || value === null) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <RemoveRoundedIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
      </Box>
    );
  }
  if (value === true) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <Box sx={{ width: 18, height: 18, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: alpha(color, isDark ? 0.18 : 0.10) }}>
          <CheckRoundedIcon sx={{ fontSize: 11, color }} />
        </Box>
      </Box>
    );
  }
  return (
    <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color, textAlign: 'center', lineHeight: 1.4 }}>
      {value}
    </Typography>
  );
}

export function PlanCards({ isDark, grad, theme }: { isDark: boolean; grad: typeof lightGradients | typeof darkGradients; theme: Theme }) {
  return (
    <StaggerContainer>
      <Box sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', xl: 'repeat(4, 1fr)' },
        gap: { xs: 1.5, sm: 2 },
        alignItems: 'stretch',
        mb: { xs: 5, sm: 7 },
      }}>
        {PLANS.map((plan) => (
          <motion.div key={plan.id} variants={fadeUp} style={{ display: 'flex' }}>
            <Box
              sx={{
                flex: 1, display: 'flex', flexDirection: 'column',
                p: { xs: 2.5, sm: 3 }, borderRadius: '16px',
                border: plan.highlight ? `2px solid ${theme.palette.primary.main}` : `1px solid ${theme.palette.divider}`,
                background: plan.highlight
                  ? isDark
                    ? `linear-gradient(160deg, ${alpha('#818cf8', 0.10)} 0%, ${alpha('#a78bfa', 0.06)} 100%)`
                    : `linear-gradient(160deg, ${alpha('#4338ca', 0.05)} 0%, ${alpha('#7c3aed', 0.03)} 100%)`
                  : theme.palette.background.paper,
                position: 'relative', overflow: 'hidden',
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
                <Box sx={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: grad.primary, borderRadius: '16px 16px 0 0' }} />
              )}

              {plan.badge && (
                <Box sx={{
                  position: 'absolute', top: 14, right: 14, px: 1.25, py: 0.4, borderRadius: '6px',
                  background: plan.id === 'growth'
                    ? `linear-gradient(135deg, #f59e0b 0%, #f97316 100%)`
                    : grad.primary,
                }}>
                  <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: '#fff', letterSpacing: '0.04em' }}>{plan.badge}</Typography>
                </Box>
              )}

              <Typography sx={{ fontWeight: 700, fontSize: '1.1rem', color: plan.color, mb: 0.5, pr: plan.badge ? 7 : 0 }}>{plan.name}</Typography>
              <Typography sx={{ color: 'text.secondary', fontSize: '0.82rem', lineHeight: 1.5, mb: 2.5 }}>{plan.tagline}</Typography>

              <Box sx={{ mb: 2.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5 }}>
                  <Typography sx={{ fontSize: plan.price ? '2rem' : '1.5rem', fontWeight: 900, color: 'text.primary', letterSpacing: '-0.03em', lineHeight: 1 }}>
                    {plan.priceLabel}
                  </Typography>
                  {plan.price && (
                    <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled', fontWeight: 500 }}>/mo</Typography>
                  )}
                </Box>
                <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled', mt: 0.4 }}>{plan.priceSub}</Typography>
              </Box>

              <Box sx={{ mb: 2.5, px: 1.5, py: 1, borderRadius: '10px', background: alpha(plan.color, isDark ? 0.10 : 0.06), border: `1px dashed ${alpha(plan.color, isDark ? 0.32 : 0.22)}`, display: 'flex', alignItems: 'center', gap: 1 }}>
                <MailRoundedIcon sx={{ fontSize: 14, color: plan.color, flexShrink: 0 }} />
                <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: plan.color }}>{plan.creditLabel}</Typography>
              </Box>

              <Box sx={{ height: '1px', background: theme.palette.divider, mb: 2 }} />

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, flex: 1 }}>
                {plan.topFeatures.map((f) => {
                  const Icon = f.icon;
                  return (
                    <Box key={f.text} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                      <Box sx={{ width: 18, height: 18, borderRadius: '50%', flexShrink: 0, mt: 0.1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: alpha(plan.color, isDark ? 0.16 : 0.09) }}>
                        <Icon sx={{ fontSize: 10, color: plan.color }} />
                      </Box>
                      <Typography sx={{ fontSize: '0.82rem', color: 'text.primary', lineHeight: 1.5 }}>{f.text}</Typography>
                    </Box>
                  );
                })}
                {plan.bullets.map((f) => (
                  <Box key={f} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                    <Box sx={{ width: 18, height: 18, borderRadius: '50%', flexShrink: 0, mt: 0.1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: alpha(plan.color, isDark ? 0.16 : 0.09) }}>
                      <CheckRoundedIcon sx={{ fontSize: 10, color: plan.color }} />
                    </Box>
                    <Typography sx={{ fontSize: '0.82rem', color: 'text.primary', lineHeight: 1.5 }}>{f}</Typography>
                  </Box>
                ))}
              </Box>

              <Button
                component={plan.ctaHref.startsWith('mailto') ? 'a' : NextLink}
                href={plan.ctaHref}
                variant={plan.ctaVariant}
                fullWidth
                sx={{
                  mt: 3, minHeight: 42, fontWeight: 600, fontSize: '0.875rem', py: 1,
                  ...(plan.highlight && {
                    background: grad.primary,
                    boxShadow: isDark ? '0 8px 24px rgba(129,140,248,0.28)' : '0 8px 24px rgba(67,56,202,0.20)',
                    '&:hover': { filter: 'brightness(1.08)', transform: 'translateY(-1px)' },
                  }),
                  ...(!plan.highlight && {
                    borderColor: alpha(plan.color, isDark ? 0.40 : 0.32),
                    color: plan.color,
                    '&:hover': { borderColor: plan.color, background: alpha(plan.color, 0.06) },
                  }),
                  transition: 'all 0.2s ease',
                }}
              >
                {plan.ctaLabel}
              </Button>
            </Box>
          </motion.div>
        ))}
      </Box>
    </StaggerContainer>
  );
}

export function ComparisonTable({ isDark, theme }: { isDark: boolean; theme: Theme }) {
  return (
    <FadeUp delay={0.1}>
      <Box>
        <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'text.disabled', textAlign: 'center', mb: 2.5 }}>
          Full feature comparison
        </Typography>
        <Box sx={{ borderRadius: '16px', border: `1px solid ${theme.palette.divider}`, overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
          <Box sx={{ minWidth: 640 }}>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1.6fr 90px 110px 90px 110px', background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.025)', borderBottom: `1px solid ${theme.palette.divider}`, px: { xs: 1.5, sm: 2.5 }, py: 1.5 }}>
              <Typography sx={{ fontSize: '0.65rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'text.disabled' }}>Feature</Typography>
              {PLANS.map((p) => (
                <Typography key={p.id} sx={{ fontSize: '0.72rem', fontWeight: 700, color: p.color, textAlign: 'center' }}>{p.name}</Typography>
              ))}
            </Box>
            {FEATURES.map((f, i) => (
              <Box
                key={f.label}
                sx={{
                  display: 'grid', gridTemplateColumns: '1.6fr 90px 110px 90px 110px',
                  px: { xs: 1.5, sm: 2.5 }, py: 1.1,
                  borderBottom: i < FEATURES.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'}` : 'none',
                  background: f.highlight ? (isDark ? 'rgba(129,140,248,0.04)' : 'rgba(67,56,202,0.025)') : 'transparent',
                  alignItems: 'center',
                  transition: 'background 0.12s',
                  '&:hover': { background: isDark ? 'rgba(255,255,255,0.025)' : 'rgba(0,0,0,0.018)' },
                }}
              >
                <Typography sx={{ fontSize: '0.78rem', color: f.highlight ? 'text.primary' : 'text.secondary', fontWeight: f.highlight ? 600 : 400, lineHeight: 1.4 }}>
                  {f.label}
                </Typography>
                <FeatureCell value={f.starter}    color={PLANS[0].color} isDark={isDark} />
                <FeatureCell value={f.pro}        color={PLANS[1].color} isDark={isDark} />
                <FeatureCell value={f.growth}     color={PLANS[2].color} isDark={isDark} />
                <FeatureCell value={f.enterprise} color={PLANS[3].color} isDark={isDark} />
              </Box>
            ))}
          </Box>
        </Box>
      </Box>
    </FadeUp>
  );
}

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
      <Box sx={{ maxWidth: 1200, mx: 'auto' }}>
        <FadeUp>
          <Box sx={{ textAlign: 'center', mb: { xs: 5, sm: 6 } }}>
            <Typography variant="overline" sx={{ color: 'primary.main', mb: 0.75, display: 'block' }}>
              Simple pricing
            </Typography>
            <Typography variant="h2" sx={{ mb: 1, fontSize: { xs: 'clamp(1.4rem, 5vw, 1.75rem)', md: '2rem' } }}>
              Start free.{' '}
              <Box component="span" sx={{ background: grad.primary, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                Scale when ready.
              </Box>
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', maxWidth: 380, mx: 'auto', fontSize: '0.875rem' }}>
              No hidden fees. No setup costs. Cancel anytime.
            </Typography>
          </Box>
        </FadeUp>

        <PlanCards isDark={isDark} grad={grad} theme={theme} />
        <ComparisonTable isDark={isDark} theme={theme} />

        {/* Enterprise CTA strip */}
        <FadeUp delay={0.15}>
          <Box sx={{ mt: { xs: 4, sm: 5 }, p: { xs: 2.5, sm: 3 }, borderRadius: '16px', background: isDark ? `linear-gradient(135deg, ${alpha('#c084fc', 0.10)} 0%, ${alpha('#818cf8', 0.06)} 100%)` : `linear-gradient(135deg, ${alpha('#7c3aed', 0.05)} 0%, ${alpha('#4338ca', 0.03)} 100%)`, border: `1px solid ${alpha('#c084fc', isDark ? 0.25 : 0.18)}`, display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, alignItems: { sm: 'center' }, gap: 2, justifyContent: 'space-between' }}>
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.5 }}>
                <AllInclusiveRoundedIcon sx={{ fontSize: 16, color: '#c084fc' }} />
                <Typography sx={{ fontWeight: 700, fontSize: '0.95rem', color: 'text.primary' }}>Need Enterprise scale?</Typography>
              </Box>
              <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary', maxWidth: 480 }}>
                Custom credits, dedicated infrastructure, custom AI training, SLA guarantees, white-label, and a dedicated customer success manager.
              </Typography>
            </Box>
            <Button
              component="a"
              href="mailto:hello@proxipilot.com"
              variant="outlined"
              sx={{ flexShrink: 0, fontWeight: 600, fontSize: '0.875rem', minHeight: 40, px: 3, borderColor: alpha('#c084fc', isDark ? 0.45 : 0.35), color: '#c084fc', '&:hover': { borderColor: '#c084fc', background: alpha('#c084fc', 0.07) }, whiteSpace: 'nowrap' }}
            >
              Contact sales →
            </Button>
          </Box>
        </FadeUp>
      </Box>
    </Box>
  );
}
