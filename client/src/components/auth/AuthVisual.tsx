'use client';

import { useEffect, useState, useRef } from 'react';
import { Box, Typography, useTheme, alpha } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import InboxRoundedIcon from '@mui/icons-material/InboxRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import { lightGradients, darkGradients } from '@/theme/palette';

const EMAILS = [
  { from: 'sarah@acme.com',    subject: 'Q4 proposal review',       time: '2m ago',  avatar: 'SA', color: '#6366f1' },
  { from: 'mike@techcorp.io',  subject: 'Partnership opportunity',  time: '5m ago',  avatar: 'MT', color: '#8b5cf6' },
  { from: 'lisa@ventures.co',  subject: 'Follow-up on our call',    time: '11m ago', avatar: 'LV', color: '#06b6d4' },
  { from: 'james@startup.dev', subject: 'Integration question',     time: '18m ago', avatar: 'JS', color: '#10b981' },
];

const PIPELINE_STEPS = [
  { icon: InboxRoundedIcon,       label: 'Email received',  ms: '< 5ms',   color: '#6366f1' },
  { icon: AutoAwesomeRoundedIcon, label: 'AI processing',   ms: '< 50ms',  color: '#8b5cf6' },
  { icon: CheckCircleRoundedIcon, label: 'Reply ready',     ms: '< 200ms', color: '#10b981' },
];

// Precise sleep — no drift
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function PulseDot({ color }: { color: string }) {
  return (
    <Box sx={{ position: 'relative', width: 6, height: 6, flexShrink: 0 }}>
      <motion.div
        animate={{ scale: [1, 2, 1], opacity: [0.5, 0, 0.5] }}
        transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
        style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: color }}
      />
      <Box sx={{ position: 'absolute', inset: '1px', borderRadius: '50%', background: color }} />
    </Box>
  );
}

export default function AuthVisual() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  const [activeEmail, setActiveEmail] = useState(0);
  const [pipelineStep, setPipelineStep] = useState(0);  // 0 = all dim, 1/2/3 = steps lit
  const [showReply, setShowReply] = useState(false);
  const cancelRef = useRef(false);

  useEffect(() => {
    cancelRef.current = false;

    const run = async () => {
      let idx = 0;

      while (!cancelRef.current) {
        // ── 1. Show new email card, reset pipeline ──────────────────────
        setActiveEmail(idx);
        setPipelineStep(0);
        setShowReply(false);

        // Wait for card enter animation to settle (350ms enter + 80ms buffer)
        await sleep(430);
        if (cancelRef.current) break;

        // ── 2. Step 1 lights up — "Email received" ──────────────────────
        setPipelineStep(1);
        await sleep(700);
        if (cancelRef.current) break;

        // ── 3. Step 2 lights up — "AI processing" ───────────────────────
        setPipelineStep(2);
        await sleep(800);
        if (cancelRef.current) break;

        // ── 4. Step 3 lights up — "Reply ready" ─────────────────────────
        setPipelineStep(3);
        await sleep(400);
        if (cancelRef.current) break;

        // ── 5. AI draft slides in ────────────────────────────────────────
        setShowReply(true);
        await sleep(2200);
        if (cancelRef.current) break;

        // ── 6. Draft slides out before card exits ────────────────────────
        setShowReply(false);
        await sleep(350);
        if (cancelRef.current) break;

        // ── 7. Advance to next email ─────────────────────────────────────
        idx = (idx + 1) % EMAILS.length;
      }
    };

    run();
    return () => { cancelRef.current = true; };
  }, []);

  const email = EMAILS[activeEmail];

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        px: 4,
        py: 5,
        position: 'relative',
        overflow: 'hidden',
        background: isDark
          ? 'linear-gradient(160deg, #0f172a 0%, #1a1040 50%, #0f172a 100%)'
          : 'linear-gradient(160deg, #eef2ff 0%, #f5f3ff 50%, #ede9fe 100%)',
      }}
    >
      {/* Background orbs */}
      <Box sx={{ position: 'absolute', top: '-20%', right: '-15%', width: '55%', height: '55%', background: isDark ? 'radial-gradient(ellipse, rgba(129,140,248,0.12) 0%, transparent 65%)' : 'radial-gradient(ellipse, rgba(67,56,202,0.09) 0%, transparent 65%)', pointerEvents: 'none' }} />
      <Box sx={{ position: 'absolute', bottom: '-15%', left: '-10%', width: '50%', height: '50%', background: isDark ? 'radial-gradient(ellipse, rgba(167,139,250,0.09) 0%, transparent 65%)' : 'radial-gradient(ellipse, rgba(124,58,237,0.07) 0%, transparent 65%)', pointerEvents: 'none' }} />

      {/* Brand mark */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        style={{ marginBottom: 32, textAlign: 'center' }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'center', mb: 1 }}>
          <Box sx={{ width: 32, height: 32, borderRadius: '9px', background: grad.primary, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <BoltRoundedIcon sx={{ color: '#fff', fontSize: 17 }} />
          </Box>
          <Typography sx={{ fontWeight: 700, fontSize: '1.05rem', letterSpacing: '-0.02em', color: 'text.primary' }}>
            Proxipilot<Box component="span" sx={{ color: 'primary.main' }}></Box>
          </Typography>
        </Box>
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', maxWidth: 240, mx: 'auto', lineHeight: 1.5 }}>
          AI replies before you even open the email
        </Typography>
      </motion.div>

      {/* Live email card */}
      <Box sx={{ width: '100%', maxWidth: 320, mb: 2.5 }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={activeEmail}
            initial={{ opacity: 0, y: 12, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12, scale: 0.97 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          >
            <Box
              sx={{
                p: 2,
                borderRadius: '12px',
                border: `1px solid ${theme.palette.divider}`,
                background: theme.palette.background.paper,
                boxShadow: isDark
                  ? '0 8px 32px rgba(0,0,0,0.35)'
                  : '0 8px 32px rgba(67,56,202,0.08)',
              }}
            >
              {/* Email header */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, mb: 1.5 }}>
                <Box sx={{ width: 32, height: 32, borderRadius: '50%', background: alpha(email.color, isDark ? 0.22 : 0.12), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: email.color }}>{email.avatar}</Typography>
                </Box>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: 'text.primary', lineHeight: 1.2 }}>{email.from}</Typography>
                  <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{email.subject}</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
                  <PulseDot color={email.color} />
                  <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>{email.time}</Typography>
                </Box>
              </Box>

              {/* Pipeline steps */}
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                {PIPELINE_STEPS.map((step, i) => {
                  const Icon = step.icon;
                  const active = pipelineStep > i;
                  return (
                    <motion.div
                      key={step.label}
                      animate={{ opacity: active ? 1 : 0.28 }}
                      transition={{ duration: 0.4, ease: 'easeOut' }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <motion.div
                          animate={{
                            background: active
                              ? alpha(step.color, isDark ? 0.22 : 0.10)
                              : alpha(theme.palette.text.disabled, 0.06),
                          }}
                          transition={{ duration: 0.4 }}
                          style={{ width: 22, height: 22, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}
                        >
                          <Icon sx={{ fontSize: 12, color: active ? step.color : theme.palette.text.disabled, transition: 'color 0.4s ease' }} />
                        </motion.div>
                        <Typography sx={{ flex: 1, fontSize: '0.7rem', color: active ? 'text.primary' : 'text.disabled', fontWeight: active ? 500 : 400, transition: 'all 0.4s ease' }}>
                          {step.label}
                        </Typography>
                        <Typography sx={{ fontSize: '0.62rem', color: active ? step.color : 'text.disabled', fontWeight: 600, transition: 'color 0.4s ease' }}>
                          {step.ms}
                        </Typography>
                      </Box>
                    </motion.div>
                  );
                })}
              </Box>

              {/* AI reply preview */}
              <AnimatePresence>
                {showReply && (
                  <motion.div
                    initial={{ opacity: 0, height: 0, marginTop: 0 }}
                    animate={{ opacity: 1, height: 'auto', marginTop: 10 }}
                    exit={{ opacity: 0, height: 0, marginTop: 0 }}
                    transition={{ duration: 0.32, ease: 'easeInOut' }}
                  >
                    <Box sx={{ p: 1.25, borderRadius: '8px', background: alpha('#10b981', isDark ? 0.10 : 0.06), border: `1px solid ${alpha('#10b981', isDark ? 0.22 : 0.14)}` }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.5 }}>
                        <AutoAwesomeRoundedIcon sx={{ fontSize: 10, color: '#10b981' }} />
                        <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.06em' }}>AI Draft Ready</Typography>
                      </Box>
                      <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', lineHeight: 1.5 }}>
                        &quot;Thank you for reaching out. I&apos;d be happy to discuss this further...&quot;
                      </Typography>
                    </Box>
                  </motion.div>
                )}
              </AnimatePresence>
            </Box>
          </motion.div>
        </AnimatePresence>
      </Box>

      {/* Inbox queue */}
      <Box sx={{ width: '100%', maxWidth: 320 }}>
        <Typography sx={{ fontSize: '0.62rem', fontWeight: 600, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.08em', mb: 1 }}>
          Inbox queue
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          {EMAILS.map((e, i) => (
            <motion.div
              key={e.from}
              animate={{ opacity: i === activeEmail ? 1 : 0.4 }}
              transition={{ duration: 0.35, ease: 'easeOut' }}
            >
              <Box
                sx={{
                  display: 'flex', alignItems: 'center', gap: 1,
                  p: '6px 8px', borderRadius: '8px',
                  background: i === activeEmail ? alpha(e.color, isDark ? 0.10 : 0.06) : 'transparent',
                  border: `1px solid ${i === activeEmail ? alpha(e.color, isDark ? 0.22 : 0.12) : 'transparent'}`,
                  transition: 'background 0.35s ease, border-color 0.35s ease',
                }}
              >
                <Box sx={{ width: 20, height: 20, borderRadius: '50%', background: alpha(e.color, isDark ? 0.20 : 0.10), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <Typography sx={{ fontSize: '0.5rem', fontWeight: 700, color: e.color }}>{e.avatar}</Typography>
                </Box>
                <Typography sx={{ flex: 1, fontSize: '0.68rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.subject}</Typography>
                {i === activeEmail && (
                  <Box sx={{ width: 5, height: 5, borderRadius: '50%', background: e.color, flexShrink: 0 }} />
                )}
              </Box>
            </motion.div>
          ))}
        </Box>
      </Box>
    </Box>
  );
}
