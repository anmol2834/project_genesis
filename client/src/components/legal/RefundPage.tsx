'use client';

import { useState, useEffect, useRef } from 'react';
import {
  Box,
  Container,
  Typography,
  IconButton,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  useTheme,
  alpha,
  useMediaQuery,
} from '@mui/material';
import {
  ArrowBackRounded,
  ExpandMoreRounded,
  ReceiptLongRounded,
  SubscriptionsRounded,
  CardGiftcardRounded,
  AutorenewRounded,
  CancelRounded,
  MoneyOffRounded,
  TokenRounded,
  ErrorOutlineRounded,
  CreditCardOffRounded,
  GavelRounded,
  StarRounded,
  PersonOffRounded,
  EditNoteRounded,
  EmailRounded,
  PaymentsRounded,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { lightGradients, darkGradients } from '@/theme/palette';

const LAST_UPDATED = 'June 7, 2026';

interface Section {
  id: string;
  number: string;
  title: string;
  icon: React.ElementType;
  content: React.ReactNode;
}

export default function RefundPage() {
  const router = useRouter();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));

  const [scrolled, setScrolled] = useState(false);
  const [expanded, setExpanded] = useState<string | false>('overview');
  const [activeNav, setActiveNav] = useState('overview');
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
      // Update active nav based on scroll position
      const scrollPos = window.scrollY + 160;
      for (const id of Object.keys(sectionRefs.current)) {
        const el = sectionRefs.current[id];
        if (el && el.offsetTop <= scrollPos) setActiveNav(id);
      }
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    setExpanded(id);
    setActiveNav(id);
    setTimeout(() => {
      const el = sectionRefs.current[id];
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
  };

  const sections: Section[] = [
    {
      id: 'overview',
      number: '01',
      title: 'Overview',
      icon: ReceiptLongRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            This Refund &amp; Cancellation Policy explains how subscription cancellations, refunds, billing disputes, credit usage, and payment-related matters are handled for Proxipilot (&quot;Proxipilot,&quot; &quot;we,&quot; &quot;our,&quot; or &quot;us&quot;).
          </Typography>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            Proxipilot is an AI-powered email automation platform that provides intelligent email management, predictive reply generation, inbox automation, and related productivity features through subscription-based services.
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>
            By purchasing, subscribing to, or using any paid Proxipilot services, you agree to this Refund &amp; Cancellation Policy.
          </Typography>
        </>
      ),
    },
    {
      id: 'subscriptions',
      number: '02',
      title: 'Subscription Services',
      icon: SubscriptionsRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            Proxipilot offers subscription plans that may include:
          </Typography>
          {['Monthly subscriptions', 'Annual subscriptions', 'Trial plans', 'Promotional or discounted plans', 'Enterprise or custom agreements'].map((item) => (
            <Box key={item} sx={{ display: 'flex', gap: 1.5, mb: 1, alignItems: 'flex-start' }}>
              <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: theme.palette.primary.main, mt: 0.75, flexShrink: 0 }} />
              <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>{item}</Typography>
            </Box>
          ))}
          <Typography variant="body2" sx={{ mt: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            Features, usage limits, AI processing capacity, storage allowances, integrations, and available credits may vary depending on the subscription plan selected. Current pricing and plan details are displayed during checkout and may be updated from time to time.
          </Typography>
        </>
      ),
    },
    {
      id: 'trials',
      number: '03',
      title: 'Free Trials',
      icon: CardGiftcardRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            Proxipilot may offer free trials to eligible users. Free trials may include:
          </Typography>
          {[
            'Limited AI-generated responses',
            'Limited automation credits',
            'Limited inbox processing',
            'Restricted access to premium features',
            'Time-based usage periods',
          ].map((item) => (
            <Box key={item} sx={{ display: 'flex', gap: 1.5, mb: 1, alignItems: 'flex-start' }}>
              <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: theme.palette.primary.main, mt: 0.75, flexShrink: 0 }} />
              <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>{item}</Typography>
            </Box>
          ))}
          <Typography variant="body2" sx={{ mt: 2, mb: 1.5, lineHeight: 1.85, color: 'text.secondary' }}>
            Free trials are intended solely for evaluating the platform. We reserve the right to modify trial duration, adjust features, limit availability, terminate trial access for abuse, or deny multiple trial registrations from the same individual or organization.
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>
            At the end of a trial period or when trial credits are exhausted, access to certain features may be restricted unless a paid subscription is purchased.
          </Typography>
        </>
      ),
    },
    {
      id: 'renewals',
      number: '04',
      title: 'Subscription Renewals',
      icon: AutorenewRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            Unless otherwise stated, subscriptions automatically renew at the end of each billing cycle. Billing cycles may include monthly renewals, annual renewals, or custom enterprise billing periods.
          </Typography>
          <Box sx={{ p: 2, borderRadius: 2, background: alpha(theme.palette.warning.main, 0.07), border: `1px solid ${alpha(theme.palette.warning.main, 0.2)}`, mb: 2 }}>
            <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5, color: theme.palette.warning.main }}>Important</Typography>
            <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary', fontSize: '0.82rem' }}>
              By purchasing a subscription, you authorize recurring billing according to your selected plan until the subscription is canceled. Renewal charges are processed using the payment method associated with your account.
            </Typography>
          </Box>
        </>
      ),
    },
    {
      id: 'cancellation',
      number: '05',
      title: 'Cancellation Policy',
      icon: CancelRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ fontWeight: 600, mb: 1, color: 'text.primary' }}>Cancel Anytime</Typography>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            You may cancel your subscription at any time through your account settings or by contacting support. Cancellation will stop future recurring billing but will not immediately terminate your access.
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 2.5 }}>
            {[
              'Access remains active until the end of the current billing period',
              'No additional charges will be applied after cancellation',
              'No cancellation penalties or fees are charged',
            ].map((item) => (
              <Box key={item} sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
                <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: theme.palette.success.main, mt: 0.75, flexShrink: 0 }} />
                <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>{item}</Typography>
              </Box>
            ))}
          </Box>
          <Typography variant="body2" sx={{ fontWeight: 600, mb: 1, color: 'text.primary' }}>Effect of Cancellation</Typography>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.85, color: 'text.secondary' }}>
            When a subscription is canceled, future renewals are stopped, existing credits may remain available until the subscription period ends, and premium features may become unavailable after expiration. Account data may be retained according to our Privacy Policy and Terms of Service.
          </Typography>
          <Box sx={{ p: 2, borderRadius: 2, background: alpha(theme.palette.info.main, 0.07), border: `1px solid ${alpha(theme.palette.info.main, 0.2)}` }}>
            <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary', fontSize: '0.82rem' }}>
              Cancellation does not automatically entitle a user to a refund.
            </Typography>
          </Box>
        </>
      ),
    },
    {
      id: 'refunds',
      number: '06',
      title: 'Refund Policy',
      icon: MoneyOffRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ fontWeight: 600, mb: 1, color: 'text.primary' }}>General Policy</Typography>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            Because Proxipilot provides digital software services, AI processing, cloud infrastructure, and immediately consumable resources, refunds are evaluated on a case-by-case basis. We strive to be fair and reasonable while protecting the platform from abuse and fraudulent refund activity.
          </Typography>
          <Typography variant="body2" sx={{ mb: 1, color: 'text.secondary', fontSize: '0.82rem' }}>Refund eligibility may depend on: time since purchase, account activity, AI resource consumption, credit usage, service utilization, technical issues experienced, and compliance with our Terms of Service.</Typography>

          <Box sx={{ mt: 2.5, mb: 2.5 }}>
            <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', sm: 'row' } }}>
              {[
                { label: 'Monthly Plans', period: '7 days', color: theme.palette.primary.main, items: ['Minimal platform usage occurred', 'Few or no credits consumed', 'Technical issues prevented use', 'Billing errors occurred'] },
                { label: 'Annual Plans', period: '14 days', color: theme.palette.secondary.main, items: ['Duration of usage considered', 'Credit consumption reviewed', 'Automation activity assessed', 'Partial refunds may apply'] },
              ].map((plan) => (
                <Box key={plan.label} sx={{ flex: 1, p: 2, borderRadius: 2, border: `1px solid ${alpha(plan.color, 0.25)}`, background: alpha(plan.color, 0.04) }}>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5, color: plan.color }}>{plan.label}</Typography>
                  <Chip label={`Review window: ${plan.period}`} size="small" sx={{ mb: 1.5, background: alpha(plan.color, 0.12), color: plan.color, fontWeight: 600, fontSize: '0.7rem', height: 22 }} />
                  <Typography variant="body2" sx={{ mb: 1, fontSize: '0.78rem', color: 'text.disabled', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>More likely when:</Typography>
                  {plan.items.map((item) => (
                    <Box key={item} sx={{ display: 'flex', gap: 1, mb: 0.5, alignItems: 'flex-start' }}>
                      <Box sx={{ width: 4, height: 4, borderRadius: '50%', background: plan.color, mt: 0.8, flexShrink: 0 }} />
                      <Typography variant="body2" sx={{ fontSize: '0.8rem', lineHeight: 1.7, color: 'text.secondary' }}>{item}</Typography>
                    </Box>
                  ))}
                </Box>
              ))}
            </Box>
          </Box>

          <Typography variant="body2" sx={{ fontWeight: 600, mb: 1, color: 'text.primary' }}>When Refund Requests May Be Denied</Typography>
          {['Significant AI processing has occurred', 'A substantial number of credits have been consumed', 'The platform has been actively used', 'The request is outside the applicable review period'].map((item) => (
            <Box key={item} sx={{ display: 'flex', gap: 1.5, mb: 0.75, alignItems: 'flex-start' }}>
              <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: theme.palette.error.main, mt: 0.75, flexShrink: 0 }} />
              <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>{item}</Typography>
            </Box>
          ))}
        </>
      ),
    },
    {
      id: 'credits',
      number: '07',
      title: 'Credit-Based Services',
      icon: TokenRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            Certain Proxipilot plans may include credits consumed through platform usage, such as AI-generated replies, email analysis, predictive automation, advanced AI processing, premium workflows, and specialized integrations.
          </Typography>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.85, color: 'text.secondary' }}>
            Credits represent access to platform resources and services. Unless required by law:
          </Typography>
          {[
            'Credits are non-refundable once consumed',
            'Credits are non-transferable',
            'Credits cannot be exchanged for cash',
            'Credits have no monetary value outside the platform',
            'Expired credits are not redeemable',
          ].map((item) => (
            <Box key={item} sx={{ display: 'flex', gap: 1.5, mb: 1, alignItems: 'flex-start' }}>
              <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: theme.palette.primary.main, mt: 0.75, flexShrink: 0 }} />
              <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>{item}</Typography>
            </Box>
          ))}
          <Typography variant="body2" sx={{ mt: 1.5, lineHeight: 1.85, color: 'text.secondary' }}>
            Refund eligibility may decrease proportionally based on the amount of credits already consumed.
          </Typography>
        </>
      ),
    },
    {
      id: 'non-refundable',
      number: '08',
      title: 'Non-Refundable Situations',
      icon: ErrorOutlineRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            Refunds are generally not available in the following circumstances:
          </Typography>
          {[
            { title: 'Subscription Renewals', desc: 'Failure to cancel before a renewal date does not automatically qualify for a refund. Users are responsible for managing their subscription status and renewal preferences.' },
            { title: 'Significant Service Usage', desc: 'Refund requests may be denied when substantial usage has already occurred, including extensive AI generation, large-scale inbox processing, high-volume automation, or significant credit consumption.' },
            { title: 'Violations of Terms', desc: 'Refunds may be denied when an account has violated our Terms of Service, Acceptable Use Policies, anti-abuse policies, or security policies.' },
            { title: 'Abuse of Refund System', desc: 'We reserve the right to deny refunds for repeated refund requests, abuse of promotional offers, multiple account creation for refunds, fraudulent activity, or attempts to circumvent platform limitations.' },
          ].map((item) => (
            <Box key={item.title} sx={{ mb: 2.5 }}>
              <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.75, color: 'text.primary' }}>{item.title}</Typography>
              <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>{item.desc}</Typography>
            </Box>
          ))}
        </>
      ),
    },
    {
      id: 'billing-errors',
      number: '09',
      title: 'Billing Errors & Duplicate Charges',
      icon: PaymentsRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            We understand that billing mistakes can occur. If you believe you were incorrectly charged, charged multiple times, or charged for a service you did not authorize, please contact us promptly.
          </Typography>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.85, color: 'text.secondary' }}>
            Verified billing errors may qualify for:
          </Typography>
          {['Full refunds', 'Partial refunds', 'Account credits', 'Charge reversals'].map((item) => (
            <Box key={item} sx={{ display: 'flex', gap: 1.5, mb: 1, alignItems: 'flex-start' }}>
              <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: theme.palette.success.main, mt: 0.75, flexShrink: 0 }} />
              <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>{item}</Typography>
            </Box>
          ))}
          <Typography variant="body2" sx={{ mt: 1.5, lineHeight: 1.85, color: 'text.secondary' }}>
            We will investigate reported billing issues in good faith and resolve legitimate errors as quickly as reasonably possible.
          </Typography>
        </>
      ),
    },
    {
      id: 'failed-payments',
      number: '10',
      title: 'Failed Payments',
      icon: CreditCardOffRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            If a payment cannot be processed:
          </Typography>
          {[
            'Subscription renewal may fail',
            'Certain premium features may be restricted',
            'Access may be suspended until payment is resolved',
            'Outstanding balances may remain due',
          ].map((item) => (
            <Box key={item} sx={{ display: 'flex', gap: 1.5, mb: 1, alignItems: 'flex-start' }}>
              <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: theme.palette.warning.main, mt: 0.75, flexShrink: 0 }} />
              <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>{item}</Typography>
            </Box>
          ))}
          <Typography variant="body2" sx={{ mt: 1.5, lineHeight: 1.85, color: 'text.secondary' }}>
            We may attempt to process payment again using the payment method associated with your account. If payment issues remain unresolved for an extended period, account access may be limited or terminated.
          </Typography>
        </>
      ),
    },
    {
      id: 'chargebacks',
      number: '11',
      title: 'Chargebacks & Payment Disputes',
      icon: GavelRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            Before initiating a chargeback or payment dispute, we encourage users to contact our support team. Many billing concerns can be resolved more quickly through direct communication.
          </Typography>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.85, color: 'text.secondary' }}>
            When a chargeback or payment dispute is initiated:
          </Typography>
          {[
            'The account may be temporarily restricted',
            'Services may be suspended during investigation',
            'Associated subscriptions may be canceled',
            'Access to premium features may be removed',
          ].map((item) => (
            <Box key={item} sx={{ display: 'flex', gap: 1.5, mb: 1, alignItems: 'flex-start' }}>
              <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: theme.palette.error.main, mt: 0.75, flexShrink: 0 }} />
              <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>{item}</Typography>
            </Box>
          ))}
          <Typography variant="body2" sx={{ mt: 1.5, lineHeight: 1.85, color: 'text.secondary' }}>
            We reserve the right to provide relevant transaction records, account activity logs, login history, usage data, and other supporting evidence to payment processors, banks, or dispute resolution providers. Fraudulent or abusive chargebacks may result in permanent account suspension.
          </Typography>
        </>
      ),
    },
    {
      id: 'exceptions',
      number: '12',
      title: 'Exceptional Circumstances',
      icon: StarRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            We understand that unusual situations may arise. Refunds may be granted outside the standard policy at our sole discretion in cases involving:
          </Typography>
          {[
            'Serious technical failures',
            'Extended service outages',
            'Duplicate transactions',
            'Unauthorized purchases',
            'Significant billing errors',
            'Legal obligations',
            'Consumer protection requirements',
          ].map((item) => (
            <Box key={item} sx={{ display: 'flex', gap: 1.5, mb: 0.75, alignItems: 'flex-start' }}>
              <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: theme.palette.primary.main, mt: 0.75, flexShrink: 0 }} />
              <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>{item}</Typography>
            </Box>
          ))}
          <Typography variant="body2" sx={{ mt: 1.5, lineHeight: 1.85, color: 'text.secondary' }}>
            Each request will be evaluated individually. Nothing in this policy limits any rights that may apply under applicable consumer protection laws.
          </Typography>
        </>
      ),
    },
    {
      id: 'termination',
      number: '13',
      title: 'Account Termination',
      icon: PersonOffRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.85, color: 'text.secondary' }}>
            If an account is suspended or terminated due to violations of our Terms of Service, abuse, fraud, security concerns, or unlawful activity, the user may not be eligible for a refund.
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>
            Unused subscription time, credits, or features may be forfeited where permitted by applicable law.
          </Typography>
        </>
      ),
    },
    {
      id: 'changes',
      number: '14',
      title: 'Changes to This Policy',
      icon: EditNoteRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.85, color: 'text.secondary' }}>
            We may update or modify this Refund &amp; Cancellation Policy from time to time. Changes become effective upon publication on our website. Continued use of Proxipilot after updates constitutes acceptance of the revised policy.
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.85, color: 'text.secondary' }}>
            Users are encouraged to review this page periodically.
          </Typography>
        </>
      ),
    },
    {
      id: 'contact',
      number: '15',
      title: 'Contact Us',
      icon: EmailRounded,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.85, color: 'text.secondary' }}>
            If you have questions regarding refunds, cancellations, billing, subscriptions, or payment disputes, please contact us:
          </Typography>
          <Box sx={{ p: 2.5, borderRadius: 2, background: alpha(theme.palette.primary.main, 0.05), border: `1px solid ${alpha(theme.palette.primary.main, 0.12)}` }}>
            <Typography variant="body2" sx={{ fontWeight: 700, mb: 1.5, color: 'text.primary', fontSize: '0.95rem' }}>Proxipilot Support</Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {[
                { label: 'Email', value: 'hello@proxipilot.com', href: 'mailto:hello@proxipilot.com' },
                { label: 'Website', value: 'https://proxipilot.com', href: 'https://proxipilot.com' },
                { label: 'Response Time', value: 'Within a reasonable timeframe' },
              ].map((item) => (
                <Box key={item.label} sx={{ display: 'flex', gap: 1.5 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.secondary', minWidth: 110, fontSize: '0.82rem' }}>{item.label}:</Typography>
                  {item.href ? (
                    <Typography component="a" href={item.href} variant="body2" sx={{ color: 'primary.main', textDecoration: 'none', fontSize: '0.82rem', '&:hover': { textDecoration: 'underline' } }}>
                      {item.value}
                    </Typography>
                  ) : (
                    <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.82rem' }}>{item.value}</Typography>
                  )}
                </Box>
              ))}
            </Box>
          </Box>
        </>
      ),
    },
  ];

  const navItems = sections.map((s) => ({ id: s.id, label: s.title, number: s.number }));

  return (
    <Box sx={{ minHeight: '100vh', background: theme.palette.background.default, pb: 8 }}>

      {/* ── Sticky Header ── */}
      <Box sx={{
        position: 'sticky', top: 0, zIndex: 1000,
        backdropFilter: scrolled ? 'blur(16px)' : 'none',
        background: scrolled ? alpha(theme.palette.background.paper, 0.9) : 'transparent',
        borderBottom: scrolled ? `1px solid ${theme.palette.divider}` : 'none',
        transition: 'all 0.25s ease',
      }}>
        <Container maxWidth="lg">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 1.75 }}>
            <IconButton
              onClick={() => router.back()}
              sx={{ background: alpha(theme.palette.primary.main, 0.08), '&:hover': { background: alpha(theme.palette.primary.main, 0.15) } }}
            >
              <ArrowBackRounded sx={{ fontSize: 20 }} />
            </IconButton>
            <Box sx={{ flex: 1 }}>
              <Typography sx={{ fontWeight: 700, fontSize: '1.05rem', color: 'text.primary', lineHeight: 1.2 }}>
                Refund &amp; Cancellation Policy
              </Typography>
              <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', mt: 0.25 }}>
                Last updated: {LAST_UPDATED}
              </Typography>
            </Box>
            <Chip
              label="15 Sections"
              size="small"
              sx={{ background: alpha(theme.palette.primary.main, 0.08), color: 'text.secondary', fontWeight: 500, fontSize: '0.72rem', height: 24 }}
            />
          </Box>
        </Container>
      </Box>

      <Container maxWidth="lg" sx={{ pt: 4, pb: 2 }}>

        {/* ── Hero ── */}
        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <Box sx={{
            background: grad.primary,
            borderRadius: 4,
            p: { xs: 3.5, sm: 5 },
            mb: 4,
            position: 'relative',
            overflow: 'hidden',
          }}>
            {/* Decorative circles */}
            <Box sx={{ position: 'absolute', top: -40, right: -40, width: 200, height: 200, borderRadius: '50%', background: 'rgba(255,255,255,0.06)', pointerEvents: 'none' }} />
            <Box sx={{ position: 'absolute', bottom: -60, right: 80, width: 150, height: 150, borderRadius: '50%', background: 'rgba(255,255,255,0.04)', pointerEvents: 'none' }} />
            <Box sx={{ position: 'relative', zIndex: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                <ReceiptLongRounded sx={{ fontSize: 36, color: 'rgba(255,255,255,0.9)' }} />
                <Typography variant="h4" sx={{ fontWeight: 800, color: '#fff', fontSize: { xs: '1.6rem', sm: '2.1rem' }, letterSpacing: '-0.02em' }}>
                  Refund &amp; Cancellation
                </Typography>
              </Box>
              <Typography sx={{ color: 'rgba(255,255,255,0.88)', fontSize: { xs: '0.88rem', sm: '0.95rem' }, lineHeight: 1.7, maxWidth: 580, mb: 3 }}>
                Clear, transparent policies for subscriptions, billing, cancellations, and refunds — designed to be fair to both you and us.
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {['Stripe Compliant', 'Paddle Compliant', 'Fair & Transparent', 'SaaS Standard'].map((badge) => (
                  <Chip
                    key={badge}
                    label={badge}
                    size="small"
                    sx={{ background: 'rgba(255,255,255,0.15)', color: '#fff', fontWeight: 600, fontSize: '0.7rem', backdropFilter: 'blur(8px)', height: 24 }}
                  />
                ))}
              </Box>
            </Box>
          </Box>
        </motion.div>

        {/* ── Layout: TOC sidebar + Content ── */}
        <Box sx={{ display: 'flex', gap: 4, alignItems: 'flex-start' }}>

          {/* ── Sticky Table of Contents (desktop only) ── */}
          {isDesktop && (
            <Box sx={{ width: 240, flexShrink: 0, position: 'sticky', top: 80 }}>
              <motion.div initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, delay: 0.15 }}>
                <Box sx={{ p: 2, borderRadius: 3, border: `1px solid ${theme.palette.divider}`, background: theme.palette.background.paper }}>
                  <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'text.disabled', mb: 1.5, px: 1 }}>
                    Contents
                  </Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
                    {navItems.map((item) => (
                      <Box
                        key={item.id}
                        onClick={() => scrollToSection(item.id)}
                        sx={{
                          display: 'flex', alignItems: 'center', gap: 1.25,
                          px: 1, py: 0.75, borderRadius: 1.5, cursor: 'pointer',
                          transition: 'all 0.15s ease',
                          background: activeNav === item.id ? alpha(theme.palette.primary.main, 0.1) : 'transparent',
                          '&:hover': { background: alpha(theme.palette.primary.main, 0.07) },
                        }}
                      >
                        <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: activeNav === item.id ? 'primary.main' : 'text.disabled', minWidth: 20, fontVariantNumeric: 'tabular-nums' }}>
                          {item.number}
                        </Typography>
                        <Typography sx={{ fontSize: '0.76rem', lineHeight: 1.4, color: activeNav === item.id ? 'primary.main' : 'text.secondary', fontWeight: activeNav === item.id ? 600 : 400 }}>
                          {item.label}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                </Box>
              </motion.div>
            </Box>
          )}

          {/* ── Main Content ── */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {sections.map((section, index) => {
                const Icon = section.icon;
                return (
                  <motion.div
                    key={section.id}
                    ref={(el) => { sectionRefs.current[section.id] = el as HTMLDivElement | null; }}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: index * 0.03 }}
                  >
                    <Accordion
                      expanded={expanded === section.id}
                      onChange={(_, isExpanded) => {
                        setExpanded(isExpanded ? section.id : false);
                        if (isExpanded) setActiveNav(section.id);
                      }}
                      sx={{
                        borderRadius: '12px !important',
                        background: theme.palette.background.paper,
                        border: `1px solid ${expanded === section.id ? alpha(theme.palette.primary.main, 0.25) : theme.palette.divider}`,
                        boxShadow: expanded === section.id ? `0 4px 24px ${alpha(theme.palette.primary.main, 0.08)}` : 'none',
                        transition: 'all 0.25s ease',
                        '&:before': { display: 'none' },
                        '&:hover': { borderColor: alpha(theme.palette.primary.main, 0.2) },
                      }}
                    >
                      <AccordionSummary
                        expandIcon={<ExpandMoreRounded sx={{ color: 'text.disabled' }} />}
                        sx={{
                          px: 2.5,
                          '& .MuiAccordionSummary-content': { display: 'flex', alignItems: 'center', gap: 2, my: 1.25 },
                        }}
                      >
                        <Typography sx={{ fontSize: '0.65rem', fontWeight: 800, color: 'text.disabled', minWidth: 24, letterSpacing: '0.05em' }}>
                          {section.number}
                        </Typography>
                        <Box sx={{
                          width: 38, height: 38, borderRadius: 2, flexShrink: 0,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          background: expanded === section.id
                            ? alpha(theme.palette.primary.main, 0.12)
                            : alpha(theme.palette.primary.main, 0.07),
                          transition: 'background 0.2s ease',
                        }}>
                          <Icon sx={{ fontSize: 19, color: expanded === section.id ? 'primary.main' : alpha(theme.palette.primary.main, 0.7) }} />
                        </Box>
                        <Typography sx={{ fontWeight: 600, fontSize: '0.92rem', color: 'text.primary', flex: 1 }}>
                          {section.title}
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails sx={{ px: { xs: 2.5, sm: 3.5 }, pb: 3, pt: 0.5 }}>
                        <Box sx={{ pl: { xs: 0, sm: 7 } }}>
                          {section.content}
                        </Box>
                      </AccordionDetails>
                    </Accordion>
                  </motion.div>
                );
              })}
            </Box>

            {/* ── Footer note ── */}
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5, delay: 0.6 }}>
              <Box sx={{ mt: 4, p: 2.5, borderRadius: 3, background: alpha(theme.palette.primary.main, 0.04), border: `1px solid ${theme.palette.divider}`, textAlign: 'center' }}>
                <Typography sx={{ fontSize: '0.8rem', color: 'text.disabled', lineHeight: 1.7 }}>
                  This policy was last updated on <strong style={{ color: theme.palette.text.secondary }}>{LAST_UPDATED}</strong>.
                  For billing questions, contact{' '}
                  <Typography component="a" href="mailto:hello@proxipilot.com" sx={{ color: 'primary.main', textDecoration: 'none', fontSize: '0.8rem', '&:hover': { textDecoration: 'underline' } }}>
                    hello@proxipilot.com
                  </Typography>
                </Typography>
              </Box>
            </motion.div>
          </Box>
        </Box>
      </Container>
    </Box>
  );
}
