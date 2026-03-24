'use client';

import { useState } from 'react';
import { Box, Typography, useTheme, alpha, Chip, useMediaQuery } from '@mui/material';
import MarkEmailReadRoundedIcon from '@mui/icons-material/MarkEmailReadRounded';
import ReplyRoundedIcon from '@mui/icons-material/ReplyRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import { motion, AnimatePresence } from 'framer-motion';
import { FadeUp } from './motion';
import { lightGradients, darkGradients } from '@/theme/palette';

const THREADS = [
  { id: 1, contact: 'Sarah Chen',    avatar: 'SC', color: '#6366f1', subject: 'Q4 Partnership Proposal',  messages: 4, unread: true,  time: '2m ago', snippet: 'Looking forward to our collaboration...',    priority: 'HIGH'   },
  { id: 2, contact: 'John Martinez', avatar: 'JM', color: '#10b981', subject: 'Demo follow-up & pricing', messages: 7, unread: false, time: '1h ago', snippet: "The demo was impressive, let's discuss...",   priority: 'MEDIUM' },
  { id: 3, contact: 'Lisa Park',     avatar: 'LP', color: '#f59e0b', subject: 'Quick call this week?',    messages: 2, unread: true,  time: '3h ago', snippet: 'Are you available Thursday afternoon?',      priority: 'LOW'    },
];

const PRIORITY_COLORS: Record<string, string> = { HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#10b981' };

export default function InboxSection() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const [selected, setSelected] = useState<number | null>(isMobile ? null : 1);
  const activeThread = THREADS.find((t) => t.id === selected);

  const handleSelect = (id: number) => setSelected(id);
  const handleBack = () => setSelected(null);

  return (
    <Box component="section" sx={{ py: { xs: 7, sm: 10, md: 14 }, px: { xs: 2, sm: 3, md: 4 } }}>
      <Box sx={{ maxWidth: 1200, mx: 'auto' }}>
        <FadeUp>
          <Box sx={{ textAlign: 'center', mb: { xs: 5, sm: 7, md: 10 } }}>
            <Typography variant="overline" sx={{ color: 'primary.main', mb: 1, display: 'block' }}>
              Smart inbox
            </Typography>
            <Typography
              variant="h2"
              sx={{ mb: 1.5, fontSize: { xs: 'clamp(1.5rem, 6vw, 2rem)', md: 'clamp(1.6rem, 4vw, 2.5rem)' } }}
            >
              Every conversation,{' '}
              <Box component="span" sx={{ background: grad.primary, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                perfectly threaded
              </Box>
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', maxWidth: 420, mx: 'auto', fontSize: { xs: '0.875rem', sm: '1rem' } }}>
              Campaign replies and inbox messages unified. AI priority scoring keeps what matters on top.
            </Typography>
          </Box>
        </FadeUp>

        <FadeUp delay={0.1}>
          <Box
            sx={{
              borderRadius: { xs: '14px', sm: '20px' },
              border: `1px solid ${theme.palette.divider}`,
              background: theme.palette.background.paper,
              overflow: 'hidden',
              boxShadow: theme.shadows[3],
              // Desktop: side-by-side. Mobile: single panel at a time
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: '260px 1fr' },
              minHeight: { xs: 'auto', md: 400 },
            }}
          >
            {/* ── Thread list ── */}
            {/* On mobile: show list when no thread selected */}
            <Box
              sx={{
                display: { xs: selected && isMobile ? 'none' : 'block', md: 'block' },
                borderRight: { md: `1px solid ${theme.palette.divider}` },
              }}
            >
              <Box sx={{ p: { xs: 1.5, sm: 2 }, borderBottom: `1px solid ${theme.palette.divider}` }}>
                <Typography sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.62rem' }}>
                  Inbox · 2 unread
                </Typography>
              </Box>

              {THREADS.map((thread) => (
                <Box
                  key={thread.id}
                  onClick={() => handleSelect(thread.id)}
                  sx={{
                    p: { xs: 1.5, sm: 2 }, cursor: 'pointer',
                    background: selected === thread.id ? alpha(theme.palette.primary.main, isDark ? 0.10 : 0.07) : 'transparent',
                    borderLeft: selected === thread.id ? `3px solid ${theme.palette.primary.main}` : '3px solid transparent',
                    transition: 'all 0.15s ease',
                    '&:hover': { background: alpha(theme.palette.text.primary, isDark ? 0.04 : 0.03) },
                    // Minimum touch target
                    minHeight: 64,
                    display: 'flex', alignItems: 'center',
                  }}
                >
                  <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start', width: '100%' }}>
                    <Box sx={{ position: 'relative', flexShrink: 0 }}>
                      <Box sx={{ width: { xs: 34, sm: 36 }, height: { xs: 34, sm: 36 }, borderRadius: '50%', background: thread.color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Typography sx={{ color: '#fff', fontSize: '0.68rem', fontWeight: 700 }}>{thread.avatar}</Typography>
                      </Box>
                      {thread.unread && (
                        <Box sx={{ position: 'absolute', top: 0, right: 0, width: 8, height: 8, borderRadius: '50%', background: theme.palette.primary.main, border: `2px solid ${theme.palette.background.paper}` }} />
                      )}
                    </Box>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.2 }}>
                        <Typography sx={{ fontWeight: thread.unread ? 700 : 500, color: 'text.primary', fontSize: { xs: '0.78rem', sm: '0.8rem' } }}>
                          {thread.contact}
                        </Typography>
                        <Typography sx={{ color: 'text.disabled', fontSize: '0.65rem', flexShrink: 0, ml: 0.5 }}>
                          {thread.time}
                        </Typography>
                      </Box>
                      <Typography sx={{ fontWeight: thread.unread ? 600 : 400, color: 'text.secondary', display: 'block', fontSize: '0.72rem', mb: 0.4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {thread.subject}
                      </Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6 }}>
                        <Box sx={{ width: 5, height: 5, borderRadius: '50%', background: PRIORITY_COLORS[thread.priority], flexShrink: 0 }} />
                        <Typography sx={{ color: 'text.disabled', fontSize: '0.65rem' }}>{thread.messages} messages</Typography>
                      </Box>
                    </Box>
                  </Box>
                </Box>
              ))}
            </Box>

            {/* ── Thread detail ── */}
            {/* On mobile: show detail when thread selected */}
            <Box sx={{ display: { xs: selected && isMobile ? 'flex' : 'none', md: 'flex' }, flexDirection: 'column' }}>
              <AnimatePresence mode="wait">
                {activeThread ? (
                  <motion.div
                    key={activeThread.id}
                    initial={{ opacity: 0, x: isMobile ? 20 : 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: isMobile ? -20 : -10 }}
                    transition={{ duration: 0.2 }}
                    style={{ display: 'flex', flexDirection: 'column', flex: 1 }}
                  >
                    {/* Thread header */}
                    <Box sx={{ p: { xs: 1.5, sm: 2.5 }, borderBottom: `1px solid ${theme.palette.divider}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
                        {/* Back button on mobile */}
                        {isMobile && (
                          <Box
                            onClick={handleBack}
                            sx={{ p: 0.5, borderRadius: '8px', cursor: 'pointer', display: 'flex', flexShrink: 0, '&:hover': { background: alpha(theme.palette.text.primary, 0.06) } }}
                          >
                            <ArrowBackRoundedIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                          </Box>
                        )}
                        <Box sx={{ minWidth: 0 }}>
                          <Typography sx={{ fontWeight: 600, fontSize: { xs: '0.85rem', sm: '1rem' }, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {activeThread.subject}
                          </Typography>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.2 }}>
                            <Typography sx={{ color: 'text.secondary', fontSize: '0.72rem' }}>{activeThread.contact}</Typography>
                            <Chip
                              label={activeThread.priority}
                              size="small"
                              sx={{
                                height: 16, fontSize: '0.58rem', fontWeight: 700,
                                background: alpha(PRIORITY_COLORS[activeThread.priority], isDark ? 0.18 : 0.10),
                                color: PRIORITY_COLORS[activeThread.priority],
                                border: `1px solid ${alpha(PRIORITY_COLORS[activeThread.priority], isDark ? 0.35 : 0.22)}`,
                              }}
                            />
                          </Box>
                        </Box>
                      </Box>
                      <Box sx={{ display: 'flex', gap: 0.75, flexShrink: 0 }}>
                        {[MarkEmailReadRoundedIcon, ReplyRoundedIcon].map((Icon, i) => (
                          <Box key={i} sx={{ p: 0.75, borderRadius: '8px', border: `1px solid ${theme.palette.divider}`, cursor: 'pointer', display: 'flex', minWidth: 32, minHeight: 32, alignItems: 'center', justifyContent: 'center', '&:hover': { background: alpha(theme.palette.text.primary, 0.04) } }}>
                            <Icon sx={{ fontSize: 15, color: 'text.secondary' }} />
                          </Box>
                        ))}
                      </Box>
                    </Box>

                    {/* Messages */}
                    <Box sx={{ flex: 1, p: { xs: 1.5, sm: 2.5 }, display: 'flex', flexDirection: 'column', gap: { xs: 1.5, sm: 2 } }}>
                      {[
                        { from: activeThread.contact, text: activeThread.snippet, time: activeThread.time, isMe: false },
                        { from: 'You (AI draft)', text: "Thank you for reaching out. I've reviewed your message and would be happy to discuss further. Are you available for a quick call this week?", time: 'Just now', isMe: true },
                      ].map((msg, i) => (
                        <Box key={i} sx={{ display: 'flex', gap: 1.25, flexDirection: msg.isMe ? 'row-reverse' : 'row' }}>
                          <Box sx={{ width: { xs: 26, sm: 28 }, height: { xs: 26, sm: 28 }, borderRadius: '50%', background: msg.isMe ? grad.primary : activeThread.color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                            {msg.isMe
                              ? <AutoAwesomeRoundedIcon sx={{ fontSize: 12, color: '#fff' }} />
                              : <Typography sx={{ color: '#fff', fontSize: '0.6rem', fontWeight: 700 }}>{activeThread.avatar}</Typography>
                            }
                          </Box>
                          <Box sx={{ maxWidth: { xs: '82%', sm: '75%' } }}>
                            <Box
                              sx={{
                                p: { xs: 1.25, sm: 1.5 },
                                borderRadius: msg.isMe ? '12px 3px 12px 12px' : '3px 12px 12px 12px',
                                background: msg.isMe
                                  ? alpha(theme.palette.primary.main, isDark ? 0.14 : 0.08)
                                  : alpha(theme.palette.text.primary, isDark ? 0.06 : 0.04),
                                border: `1px solid ${msg.isMe ? alpha(theme.palette.primary.main, isDark ? 0.25 : 0.14) : theme.palette.divider}`,
                              }}
                            >
                              <Typography sx={{ fontSize: { xs: '0.76rem', sm: '0.8rem' }, color: 'text.primary', lineHeight: 1.6 }}>{msg.text}</Typography>
                            </Box>
                            <Typography sx={{ color: 'text.disabled', fontSize: '0.65rem', mt: 0.4, display: 'block', textAlign: msg.isMe ? 'right' : 'left' }}>
                              {msg.isMe && <AutoAwesomeRoundedIcon sx={{ fontSize: 9, mr: 0.4, verticalAlign: 'middle', color: 'primary.main' }} />}
                              {msg.from} · {msg.time}
                            </Typography>
                          </Box>
                        </Box>
                      ))}
                    </Box>
                  </motion.div>
                ) : (
                  // Desktop empty state
                  <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Typography sx={{ color: 'text.disabled', fontSize: '0.85rem' }}>Select a conversation</Typography>
                  </motion.div>
                )}
              </AnimatePresence>
            </Box>
          </Box>
        </FadeUp>
      </Box>
    </Box>
  );
}
