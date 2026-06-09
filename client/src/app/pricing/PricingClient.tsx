'use client';

import { Box, Typography, Button, useTheme, alpha } from '@mui/material';
import { motion } from 'framer-motion';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import RemoveRoundedIcon from '@mui/icons-material/RemoveRounded';
import AllInclusiveRoundedIcon from '@mui/icons-material/AllInclusiveRounded';
import MailRoundedIcon from '@mui/icons-material/MailRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import ShieldRoundedIcon from '@mui/icons-material/ShieldRounded';
import SupportAgentRoundedIcon from '@mui/icons-material/SupportAgentRounded';
import SpeedRoundedIcon from '@mui/icons-material/SpeedRounded';
import NextLink from 'next/link';
import Navbar from '@/components/landing/Navbar';
import Footer from '@/components/landing/Footer';
import { lightGradients, darkGradients } from '@/theme/palette';
import { PLANS, FEATURES } from '@/components/landing/PricingSection';

const MotionBox = motion.create(Box);

type FeatureValue = boolean | string | null;

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
        <Box sx={{ width: 20, height: 20, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: alpha(color, isDark ? 0.18 : 0.10) }}>
          <CheckRoundedIcon sx={{ fontSize: 12, color }} />
        </Box>
      </Box>
    );
  }
  return (
    <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color, textAlign: 'center', lineHeight: 1.4 }}>
      {value}
    </Typography>
  );
}

const trustItems = [
  { icon: ShieldRoundedIcon,       text: 'AES-256 encryption',       sub: 'Your data is always secure' },
  { icon: SpeedRoundedIcon,        text: 'Blazing-fast processing',   sub: 'Replies before you open inbox' },
  { icon: SupportAgentRoundedIcon, text: 'Real human support',        sub: 'Not just a chatbot' },
  { icon: BoltRoundedIcon,         text: 'Cancel anytime',            sub: 'No lock-in contracts' },
];

const faqs = [
  { q: 'What is an email processing credit?', a: 'One credit = one email processed by our AI engine. This includes reading, understanding context, and generating a smart reply draft.' },
  { q: 'Can I change my plan later?', a: 'Yes. You can upgrade or downgrade your plan at any time from your billing settings. Changes take effect on your next billing cycle.' },
  { q: 'Is there a free trial for paid plans?', a: 'The Starter plan is permanently free and gives you 50 credits to experience the full AI workflow. No credit card required.' },
  { q: 'What happens when I run out of credits?', a: 'You\'ll receive an alert when you\'re running low. You can purchase top-up credit packs or upgrade to a higher plan at any time.' },
  { q: 'Do unused credits roll over?', a: 'Credits reset monthly on your billing date. They do not roll over, but you can always top up if you need more before the reset.' },
  { q: 'How does Enterprise pricing work?', a: 'Enterprise is fully custom — we\'ll work with you to design a plan that fits your volume, compliance requirements, and team structure. Contact sales to get started.' },
];

export default function PricingClient() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  return (
    <Box sx={{ minHeight: '100vh', background: theme.palette.background.default }}>
      <Navbar />

      {/* ── Hero ── */}
      <Box
        component="section"
        sx={{
          pt: { xs: 10, sm: 14, md: 16 },
          pb: { xs: 6, sm: 8 },
          px: { xs: 2, sm: 3 },
          textAlign: 'center',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* background blobs */}
        <Box sx={{ position: 'absolute', inset: 0, zIndex: 0, pointerEvents: 'none' }}>
          <Box sx={{ position: 'absolute', top: '0%', left: '20%', width: { xs: 280, md: 500 }, height: { xs: 280, md: 500 }, background: isDark ? 'radial-gradient(circle, rgba(129,140,248,0.12) 0%, transparent 65%)' : 'radial-gradient(circle, rgba(67,56,202,0.07) 0%, transparent 65%)' }} />
          <Box sx={{ position: 'absolute', top: '10%', right: '15%', width: { xs: 200, md: 380 }, height: { xs: 200, md: 380 }, background: isDark ? 'radial-gradient(circle, rgba(192,132,252,0.10) 0%, transparent 65%)' : 'radial-gradient(circle, rgba(124,58,237,0.05) 0%, transparent 65%)' }} />
        </Box>

        <Box sx={{ position: 'relative', zIndex: 1, maxWidth: 680, mx: 'auto' }}>
          <MotionBox
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            sx={{ display: 'inline-flex', alignItems: 'center', gap: 1, px: 2, py: 0.6, borderRadius: '50px', background: isDark ? alpha('#818cf8', 0.12) : alpha('#4338ca', 0.07), border: `1px solid ${alpha('#818cf8', 0.25)}`, mb: 2.5 }}
          >
            <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: '#818cf8', boxShadow: '0 0 8px rgba(129,140,248,0.7)' }} />
            <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: 'primary.main' }}>Transparent pricing, no surprises</Typography>
          </MotionBox>

          <MotionBox initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.55, delay: 0.05 }}>
            <Typography
              variant="h1"
              sx={{
                fontSize: { xs: '2rem', sm: '2.75rem', md: '3.25rem' },
                fontWeight: 900,
                lineHeight: 1.1,
                letterSpacing: '-0.03em',
                mb: 2,
              }}
            >
              Plans that grow{' '}
              <Box
                component="span"
                sx={{ background: grad.primary, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}
              >
                with you
              </Box>
            </Typography>
          </MotionBox>

          <MotionBox initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }}>
            <Typography sx={{ fontSize: { xs: '1rem', md: '1.1rem' }, color: 'text.secondary', lineHeight: 1.7, mb: 3 }}>
              Start for free. Upgrade when your team is ready. No hidden fees, no setup costs, cancel anytime.
            </Typography>
          </MotionBox>

          <MotionBox initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.15 }}>
            <Box sx={{ display: 'flex', gap: 1.5, justifyContent: 'center', flexWrap: 'wrap' }}>
              <Button
                component={NextLink}
                href="/sign-up"
                variant="contained"
                sx={{ fontWeight: 700, px: 3.5, py: 1.25, fontSize: '0.95rem', background: grad.primary, boxShadow: isDark ? '0 8px 28px rgba(129,140,248,0.3)' : '0 8px 28px rgba(67,56,202,0.22)', '&:hover': { filter: 'brightness(1.08)' } }}
              >
                Start for free
              </Button>
              <Button
                component="a"
                href="mailto:hello@proxipilot.com"
                variant="outlined"
                sx={{ fontWeight: 600, px: 3, py: 1.25, fontSize: '0.95rem', borderColor: alpha(theme.palette.primary.main, 0.4), color: 'primary.main', '&:hover': { borderColor: 'primary.main', background: alpha(theme.palette.primary.main, 0.05) } }}
              >
                Talk to sales
              </Button>
            </Box>
          </MotionBox>
        </Box>
      </Box>

      {/* ── Plan cards ── */}
      <Box
        component="section"
        sx={{ px: { xs: 2, sm: 3, md: 4 }, pb: { xs: 6, sm: 8 }, maxWidth: 1300, mx: 'auto' }}
      >
        <Box sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', xl: 'repeat(4, 1fr)' },
          gap: { xs: 2, sm: 2.5 },
          alignItems: 'stretch',
        }}>
          {PLANS.map((plan, idx) => (
            <MotionBox
              key={plan.id}
              initial={{ opacity: 0, y: 32 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 + idx * 0.08 }}
              sx={{
                display: 'flex',
                flexDirection: 'column',
                p: { xs: 2.5, sm: 3 },
                borderRadius: '20px',
                border: plan.highlight ? `2px solid ${theme.palette.primary.main}` : `1px solid ${theme.palette.divider}`,
                background: plan.highlight
                  ? isDark
                    ? `linear-gradient(160deg, ${alpha('#818cf8', 0.12)} 0%, ${alpha('#a78bfa', 0.07)} 100%)`
                    : `linear-gradient(160deg, ${alpha('#4338ca', 0.06)} 0%, ${alpha('#7c3aed', 0.04)} 100%)`
                  : theme.palette.background.paper,
                position: 'relative',
                overflow: 'hidden',
                transition: 'all 0.25s ease',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: plan.highlight
                    ? `0 16px 40px ${alpha(theme.palette.primary.main, isDark ? 0.22 : 0.14)}`
                    : `0 12px 32px ${alpha('#000', isDark ? 0.3 : 0.08)}`,
                },
              }}
            >
              {plan.highlight && (
                <Box sx={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, background: grad.primary, borderRadius: '20px 20px 0 0' }} />
              )}

              {plan.badge && (
                <Box sx={{
                  position: 'absolute', top: 16, right: 16, px: 1.25, py: 0.5, borderRadius: '8px',
                  background: plan.id === 'growth'
                    ? 'linear-gradient(135deg, #f59e0b 0%, #f97316 100%)'
                    : grad.primary,
                }}>
                  <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: '#fff', letterSpacing: '0.05em' }}>{plan.badge}</Typography>
                </Box>
              )}

              {/* Plan header */}
              <Typography sx={{ fontWeight: 800, fontSize: '1.15rem', color: plan.color, mb: 0.4, pr: plan.badge ? 8 : 0 }}>{plan.name}</Typography>
              <Typography sx={{ color: 'text.secondary', fontSize: '0.83rem', lineHeight: 1.5, mb: 2.5 }}>{plan.tagline}</Typography>

              {/* Price */}
              <Box sx={{ mb: 2.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5 }}>
                  <Typography sx={{ fontSize: plan.price ? '2.4rem' : '1.75rem', fontWeight: 900, color: 'text.primary', letterSpacing: '-0.04em', lineHeight: 1 }}>
                    {plan.priceLabel}
                  </Typography>
                  {plan.price && (
                    <Typography sx={{ fontSize: '0.8rem', color: 'text.disabled', fontWeight: 500 }}>/mo</Typography>
                  )}
                </Box>
                <Typography sx={{ fontSize: '0.72rem', color: 'text.disabled', mt: 0.5 }}>{plan.priceSub}</Typography>
              </Box>

              {/* Credit pill */}
              <Box sx={{ mb: 2.5, px: 1.5, py: 1, borderRadius: '10px', background: alpha(plan.color, isDark ? 0.10 : 0.06), border: `1px dashed ${alpha(plan.color, isDark ? 0.35 : 0.25)}`, display: 'flex', alignItems: 'center', gap: 1 }}>
                <MailRoundedIcon sx={{ fontSize: 15, color: plan.color, flexShrink: 0 }} />
                <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: plan.color }}>{plan.creditLabel}</Typography>
              </Box>

              <Box sx={{ height: '1px', background: theme.palette.divider, mb: 2 }} />

              {/* Feature list */}
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.1, flex: 1 }}>
                {plan.topFeatures.map((f) => {
                  const Icon = f.icon;
                  return (
                    <Box key={f.text} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.1 }}>
                      <Box sx={{ width: 20, height: 20, borderRadius: '50%', flexShrink: 0, mt: 0.05, display: 'flex', alignItems: 'center', justifyContent: 'center', background: alpha(plan.color, isDark ? 0.16 : 0.09) }}>
                        <Icon sx={{ fontSize: 11, color: plan.color }} />
                      </Box>
                      <Typography sx={{ fontSize: '0.84rem', color: 'text.primary', lineHeight: 1.5 }}>{f.text}</Typography>
                    </Box>
                  );
                })}
                {plan.bullets.map((f) => (
                  <Box key={f} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.1 }}>
                    <Box sx={{ width: 20, height: 20, borderRadius: '50%', flexShrink: 0, mt: 0.05, display: 'flex', alignItems: 'center', justifyContent: 'center', background: alpha(plan.color, isDark ? 0.16 : 0.09) }}>
                      <CheckRoundedIcon sx={{ fontSize: 11, color: plan.color }} />
                    </Box>
                    <Typography sx={{ fontSize: '0.84rem', color: 'text.primary', lineHeight: 1.5 }}>{f}</Typography>
                  </Box>
                ))}
              </Box>

              <Button
                component={plan.ctaHref.startsWith('mailto') ? 'a' : NextLink}
                href={plan.ctaHref}
                variant={plan.ctaVariant}
                fullWidth
                sx={{
                  mt: 3, minHeight: 46, fontWeight: 700, fontSize: '0.9rem',
                  borderRadius: '10px',
                  ...(plan.highlight && {
                    background: grad.primary,
                    boxShadow: isDark ? '0 8px 24px rgba(129,140,248,0.28)' : '0 8px 24px rgba(67,56,202,0.20)',
                    '&:hover': { filter: 'brightness(1.08)', transform: 'translateY(-1px)' },
                  }),
                  ...(!plan.highlight && {
                    borderColor: alpha(plan.color, isDark ? 0.45 : 0.35),
                    color: plan.color,
                    '&:hover': { borderColor: plan.color, background: alpha(plan.color, 0.06) },
                  }),
                  transition: 'all 0.2s ease',
                }}
              >
                {plan.ctaLabel}
              </Button>
            </MotionBox>
          ))}
        </Box>
      </Box>

      {/* ── Trust badges ── */}
      <Box
        component="section"
        sx={{
          px: { xs: 2, sm: 3 },
          pb: { xs: 6, sm: 8 },
          maxWidth: 1000,
          mx: 'auto',
        }}
      >
        <Box sx={{
          display: 'grid',
          gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
          gap: { xs: 1.5, sm: 2 },
        }}>
          {trustItems.map((item, i) => {
            const Icon = item.icon;
            return (
              <MotionBox
                key={item.text}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.05 * i }}
                sx={{
                  p: { xs: 2, sm: 2.5 },
                  borderRadius: '14px',
                  border: `1px solid ${theme.palette.divider}`,
                  background: theme.palette.background.paper,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  textAlign: 'center',
                  gap: 1,
                  transition: 'all 0.2s',
                  '&:hover': { transform: 'translateY(-2px)', boxShadow: theme.shadows[2] },
                }}
              >
                <Box sx={{ width: 40, height: 40, borderRadius: '12px', background: alpha(theme.palette.primary.main, isDark ? 0.12 : 0.07), display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Icon sx={{ fontSize: 20, color: 'primary.main' }} />
                </Box>
                <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', color: 'text.primary' }}>{item.text}</Typography>
                <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', lineHeight: 1.4 }}>{item.sub}</Typography>
              </MotionBox>
            );
          })}
        </Box>
      </Box>

      {/* ── Full comparison table ── */}
      <Box
        component="section"
        sx={{ px: { xs: 2, sm: 3, md: 4 }, pb: { xs: 6, sm: 8 }, maxWidth: 1100, mx: 'auto' }}
      >
        <MotionBox initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'text.disabled', textAlign: 'center', mb: 1 }}>
            Compare all features
          </Typography>
          <Typography variant="h3" sx={{ textAlign: 'center', fontWeight: 800, fontSize: { xs: '1.4rem', md: '1.75rem' }, mb: { xs: 3, sm: 4 } }}>
            Full feature{' '}
            <Box component="span" sx={{ background: grad.primary, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
              comparison
            </Box>
          </Typography>

          <Box sx={{ borderRadius: '16px', border: `1px solid ${theme.palette.divider}`, overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
            <Box sx={{ minWidth: 640 }}>
              {/* Header */}
              <Box sx={{ display: 'grid', gridTemplateColumns: '1.8fr 90px 110px 90px 110px', background: isDark ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.03)', borderBottom: `1px solid ${theme.palette.divider}`, px: { xs: 2, sm: 3 }, py: 2 }}>
                <Typography sx={{ fontSize: '0.68rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'text.disabled' }}>Feature</Typography>
                {PLANS.map((p) => (
                  <Box key={p.id} sx={{ textAlign: 'center' }}>
                    <Typography sx={{ fontSize: '0.75rem', fontWeight: 800, color: p.color }}>{p.name}</Typography>
                    {p.price && <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mt: 0.2 }}>${p.price}/mo</Typography>}
                    {!p.price && <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mt: 0.2 }}>{p.priceLabel}</Typography>}
                  </Box>
                ))}
              </Box>

              {/* Rows */}
              {FEATURES.map((f, i) => (
                <Box
                  key={f.label}
                  sx={{
                    display: 'grid', gridTemplateColumns: '1.8fr 90px 110px 90px 110px',
                    px: { xs: 2, sm: 3 }, py: 1.2,
                    borderBottom: i < FEATURES.length - 1 ? `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'}` : 'none',
                    background: f.highlight ? (isDark ? 'rgba(129,140,248,0.05)' : 'rgba(67,56,202,0.03)') : 'transparent',
                    alignItems: 'center',
                    transition: 'background 0.12s',
                    '&:hover': { background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)' },
                  }}
                >
                  <Typography sx={{ fontSize: '0.8rem', color: f.highlight ? 'text.primary' : 'text.secondary', fontWeight: f.highlight ? 600 : 400, lineHeight: 1.4 }}>
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
        </MotionBox>
      </Box>

      {/* ── FAQ ── */}
      <Box
        component="section"
        sx={{ px: { xs: 2, sm: 3 }, pb: { xs: 8, sm: 10 }, maxWidth: 820, mx: 'auto' }}
      >
        <MotionBox initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'text.disabled', textAlign: 'center', mb: 1 }}>
            Got questions?
          </Typography>
          <Typography variant="h3" sx={{ textAlign: 'center', fontWeight: 800, fontSize: { xs: '1.4rem', md: '1.75rem' }, mb: { xs: 3, sm: 4 } }}>
            Frequently asked{' '}
            <Box component="span" sx={{ background: grad.primary, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
              questions
            </Box>
          </Typography>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {faqs.map((faq, i) => (
              <MotionBox
                key={i}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.05 * i }}
                sx={{
                  p: { xs: 2.5, sm: 3 },
                  borderRadius: '14px',
                  border: `1px solid ${theme.palette.divider}`,
                  background: theme.palette.background.paper,
                }}
              >
                <Typography sx={{ fontWeight: 700, fontSize: '0.92rem', color: 'text.primary', mb: 1 }}>
                  {faq.q}
                </Typography>
                <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary', lineHeight: 1.7 }}>
                  {faq.a}
                </Typography>
              </MotionBox>
            ))}
          </Box>
        </MotionBox>
      </Box>

      {/* ── Enterprise CTA banner ── */}
      <Box
        component="section"
        sx={{ px: { xs: 2, sm: 3, md: 4 }, pb: { xs: 8, sm: 12 }, maxWidth: 900, mx: 'auto' }}
      >
        <MotionBox
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          sx={{
            p: { xs: 3, sm: 5 },
            borderRadius: '24px',
            background: isDark
              ? `linear-gradient(135deg, ${alpha('#c084fc', 0.14)} 0%, ${alpha('#818cf8', 0.09)} 100%)`
              : `linear-gradient(135deg, ${alpha('#7c3aed', 0.06)} 0%, ${alpha('#4338ca', 0.04)} 100%)`,
            border: `1px solid ${alpha('#c084fc', isDark ? 0.28 : 0.20)}`,
            textAlign: 'center',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          <Box sx={{ position: 'absolute', top: -40, right: -40, width: 180, height: 180, borderRadius: '50%', background: isDark ? alpha('#c084fc', 0.08) : alpha('#7c3aed', 0.04), pointerEvents: 'none' }} />
          <Box sx={{ position: 'absolute', bottom: -30, left: -30, width: 140, height: 140, borderRadius: '50%', background: isDark ? alpha('#818cf8', 0.07) : alpha('#4338ca', 0.03), pointerEvents: 'none' }} />

          <Box sx={{ position: 'relative', zIndex: 1 }}>
            <Box sx={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 56, height: 56, borderRadius: '16px', background: alpha('#c084fc', isDark ? 0.18 : 0.10), mb: 2 }}>
              <AllInclusiveRoundedIcon sx={{ fontSize: 28, color: '#c084fc' }} />
            </Box>
            <Typography variant="h3" sx={{ fontWeight: 800, fontSize: { xs: '1.4rem', md: '1.9rem' }, mb: 1.5, color: 'text.primary' }}>
              Need something custom?
            </Typography>
            <Typography sx={{ fontSize: { xs: '0.9rem', md: '1rem' }, color: 'text.secondary', maxWidth: 520, mx: 'auto', lineHeight: 1.7, mb: 3 }}>
              Custom credits, dedicated infrastructure, custom AI training, white-label options, SLA guarantees, and a dedicated customer success manager.
            </Typography>
            <Box sx={{ display: 'flex', gap: 1.5, justifyContent: 'center', flexWrap: 'wrap' }}>
              <Button
                component="a"
                href="mailto:hello@proxipilot.com"
                variant="contained"
                sx={{ fontWeight: 700, px: 3.5, py: 1.25, fontSize: '0.95rem', background: `linear-gradient(135deg, #c084fc 0%, #818cf8 100%)`, boxShadow: isDark ? '0 8px 28px rgba(192,132,252,0.3)' : '0 8px 28px rgba(124,58,237,0.2)', '&:hover': { filter: 'brightness(1.08)', transform: 'translateY(-1px)' }, transition: 'all 0.2s' }}
              >
                Contact sales →
              </Button>
              <Button
                component={NextLink}
                href="/sign-up"
                variant="outlined"
                sx={{ fontWeight: 600, px: 3, py: 1.25, fontSize: '0.95rem', borderColor: alpha('#c084fc', isDark ? 0.45 : 0.35), color: '#c084fc', '&:hover': { borderColor: '#c084fc', background: alpha('#c084fc', 0.07) } }}
              >
                Start free instead
              </Button>
            </Box>
          </Box>
        </MotionBox>
      </Box>

      <Footer />
    </Box>
  );
}
