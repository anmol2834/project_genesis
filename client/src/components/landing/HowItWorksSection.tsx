'use client';

import { Box, Typography, useTheme, alpha } from '@mui/material';
import InboxRoundedIcon from '@mui/icons-material/InboxRounded';
import PsychologyRoundedIcon from '@mui/icons-material/PsychologyRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import { motion } from 'framer-motion';
import { FadeUp, StaggerContainer, fadeUp } from './motion';
import { lightGradients, darkGradients } from '@/theme/palette';

const STEPS = [
  { icon: InboxRoundedIcon,       label: 'Email arrives',   desc: 'Works with Gmail, Outlook, and any SMTP provider',       color: '#6366f1', s: '< 1s'   },
  { icon: PsychologyRoundedIcon,  label: 'AI processes',    desc: 'Intent detection, tone analysis, context retrieval',     color: '#8b5cf6', s: '< 2s'  },
  { icon: AutoAwesomeRoundedIcon, label: 'Reply generated', desc: 'Predictive draft ready before you open the email',       color: '#06b6d4', s: '< 3s' },
  { icon: SendRoundedIcon,        label: 'Sent instantly',  desc: 'One-click send or full auto-reply mode',                 color: '#10b981', s: '< 1s'  },
];

const PERF_BARS = [
  { label: 'Webhook ack',    val: 5,   max: 200, color: '#6366f1' },
  { label: 'AI generation',  val: 180, max: 200, color: '#8b5cf6' },
  { label: 'DB write',       val: 12,  max: 200, color: '#06b6d4' },
  { label: 'Total pipeline', val: 25,  max: 200, color: '#10b981' },
];

function PulseDot({ color }: { color: string }) {
  return (
    <Box sx={{ position: 'relative', width: 8, height: 8, flexShrink: 0 }}>
      <motion.div
        animate={{ scale: [1, 1.8, 1], opacity: [0.6, 0, 0.6] }}
        transition={{ repeat: Infinity, duration: 1.8, ease: 'easeInOut' }}
        style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: color }}
      />
      <Box sx={{ position: 'absolute', inset: '1.5px', borderRadius: '50%', background: color }} />
    </Box>
  );
}

export default function HowItWorksSection() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  return (
    <Box
      id="how-it-works"
      component="section"
      sx={{ py: { xs: 7, sm: 10, md: 14 }, px: { xs: 2, sm: 3, md: 4 } }}
    >
      <Box sx={{ maxWidth: 1200, mx: 'auto' }}>
        <FadeUp>
          <Box sx={{ textAlign: 'center', mb: { xs: 5, sm: 7, md: 10 } }}>
            <Typography variant="overline" sx={{ color: 'primary.main', mb: 1, display: 'block' }}>
              Zero-blocking pipeline
            </Typography>
            <Typography
              variant="h2"
              sx={{ mb: 1.5, fontSize: { xs: 'clamp(1.5rem, 6vw, 2rem)', md: 'clamp(1.6rem, 4vw, 2.5rem)' } }}
            >
              From inbox to reply in{' '}
              <Box component="span" sx={{ background: grad.primary, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                milliseconds
              </Box>
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', maxWidth: 420, mx: 'auto', fontSize: { xs: '0.875rem', sm: '1rem' } }}>
              A fire-and-forget architecture that never blocks. Every stage runs in parallel.
            </Typography>
          </Box>
        </FadeUp>

        {/* Step cards */}
        <StaggerContainer>
          <Box
            sx={{
              display: 'grid',
              // 1 col on mobile, 2 on sm, 4 on lg
              gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: 'repeat(4, 1fr)' },
              gap: { xs: 1.5, sm: 2 },
              position: 'relative',
            }}
          >
            {STEPS.map((step, i) => {
              const Icon = step.icon;
              return (
                <motion.div key={step.label} variants={fadeUp}>
                  <Box
                    sx={{
                      p: { xs: 2.5, sm: 3 },
                      borderRadius: '14px',
                      border: `1px solid ${theme.palette.divider}`,
                      background: theme.palette.background.paper,
                      position: 'relative',
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        borderColor: alpha(step.color, isDark ? 0.5 : 0.35),
                        boxShadow: `0 6px 24px ${alpha(step.color, isDark ? 0.16 : 0.09)}`,
                        transform: 'translateY(-2px)',
                      },
                    }}
                  >
                    {/* Step number */}
                    <Box sx={{ position: 'absolute', top: 10, right: 12 }}>
                      <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, color: alpha(step.color, isDark ? 0.55 : 0.4) }}>
                        0{i + 1}
                      </Typography>
                    </Box>

                    {/* Icon */}
                    <Box sx={{ width: { xs: 40, sm: 44 }, height: { xs: 40, sm: 44 }, borderRadius: '10px', mb: 2, background: alpha(step.color, isDark ? 0.15 : 0.09), display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Icon sx={{ color: step.color, fontSize: { xs: 20, sm: 22 } }} />
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.75 }}>
                      <PulseDot color={step.color} />
                      <Typography sx={{ color: step.color, fontWeight: 700, fontSize: '0.7rem' }}>{step.s}</Typography>
                    </Box>

                    <Typography variant="h6" sx={{ mb: 0.5, fontSize: { xs: '0.9rem', sm: '1rem' } }}>{step.label}</Typography>
                    <Typography variant="body2" sx={{ color: 'text.secondary', lineHeight: 1.6, fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>{step.desc}</Typography>

                    {/* Connector arrow — desktop only */}
                    {i < STEPS.length - 1 && (
                      <Box sx={{ display: { xs: 'none', lg: 'block' }, position: 'absolute', right: -15, top: '50%', transform: 'translateY(-50%)', zIndex: 2 }}>
                        <motion.div animate={{ x: [0, 3, 0] }} transition={{ repeat: Infinity, duration: 1.5, ease: 'easeInOut', delay: i * 0.3 }}>
                          <Box sx={{ color: 'text.disabled', fontSize: '1rem', lineHeight: 1 }}>→</Box>
                        </motion.div>
                      </Box>
                    )}
                  </Box>
                </motion.div>
              );
            })}
          </Box>
        </StaggerContainer>

        {/* Performance bars */}
        <FadeUp delay={0.2}>
          <Box
            sx={{
              mt: { xs: 4, sm: 6 },
              p: { xs: 2, sm: 3 },
              borderRadius: '14px',
              background: alpha(theme.palette.primary.main, isDark ? 0.06 : 0.04),
              border: `1px solid ${alpha(theme.palette.primary.main, isDark ? 0.14 : 0.09)}`,
              // 2-col grid on mobile, flex-wrap on larger
              display: 'grid',
              gridTemplateColumns: { xs: '1fr 1fr', sm: 'repeat(4, 1fr)' },
              gap: { xs: 2, sm: 3 },
            }}
          >
            {PERF_BARS.map((item) => (
              <Box key={item.label}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography sx={{ color: 'text.secondary', fontWeight: 500, fontSize: { xs: '0.7rem', sm: '0.75rem' } }}>{item.label}</Typography>
                  <Typography sx={{ color: item.color, fontWeight: 700, fontSize: { xs: '0.7rem', sm: '0.75rem' } }}>{item.val}s</Typography>
                </Box>
                <Box sx={{ height: 4, borderRadius: '9999px', background: alpha(item.color, isDark ? 0.20 : 0.12), overflow: 'hidden' }}>
                  <motion.div
                    initial={{ width: 0 }}
                    whileInView={{ width: `${(item.val / item.max) * 100}%` }}
                    viewport={{ once: true }}
                    transition={{ duration: 1, delay: 0.3, ease: 'easeOut' }}
                    style={{ height: '100%', borderRadius: 9999, background: item.color }}
                  />
                </Box>
              </Box>
            ))}
          </Box>
        </FadeUp>
      </Box>
    </Box>
  );
}
