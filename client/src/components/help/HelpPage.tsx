'use client';
import { useState, useRef, useEffect, useMemo } from 'react';
import {
  Box, Typography, useTheme, alpha, InputBase, IconButton, Modal,
} from '@mui/material';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import RocketLaunchRoundedIcon from '@mui/icons-material/RocketLaunchRounded';
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded';
import InboxRoundedIcon from '@mui/icons-material/InboxRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import ExtensionRoundedIcon from '@mui/icons-material/ExtensionRounded';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';
import ChatRoundedIcon from '@mui/icons-material/ChatRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import ConfirmationNumberRoundedIcon from '@mui/icons-material/ConfirmationNumberRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import ChevronRightRoundedIcon from '@mui/icons-material/ChevronRightRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import PlayCircleRoundedIcon from '@mui/icons-material/PlayCircleRounded';
import FiberManualRecordRoundedIcon from '@mui/icons-material/FiberManualRecordRounded';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import ArticleRoundedIcon from '@mui/icons-material/ArticleRounded';
import { lightGradients, darkGradients } from '@/theme/palette';
import {
  HELP_CATEGORIES, HELP_ARTICLES, HELP_TICKETS, SYSTEM_STATUS,
  SEARCH_SUGGESTIONS, AI_QUICK_PROMPTS, VIDEO_TUTORIALS,
} from './helpData';

const CAT_ICONS: Record<string, React.ElementType> = {
  start: RocketLaunchRoundedIcon,
  campaign: CampaignRoundedIcon,
  inbox: InboxRoundedIcon,
  leads: PeopleRoundedIcon,
  integrations: ExtensionRoundedIcon,
  settings: SettingsRoundedIcon,
};

const AI_RESPONSES: Record<string, string> = {
  default: 'I can help with that. Check your account settings or reconnect the integration. Want a step-by-step guide?',
  campaign: 'Campaigns pause due to daily send limits or account health. Go to Campaigns, select your campaign, check the Status tab.',
  gmail: 'To reconnect Gmail: Email Accounts, click your account, Reconnect. Grant all permissions during OAuth.',
  import: 'CSV imports need: email, first_name, last_name columns minimum. Go to Leads, Import CSV, drag your file.',
  open: 'Improve open rates: personalize subject lines, send 9-11 AM local time, warm up email accounts.',
};

function getAIResponse(text: string): string {
  const lower = text.toLowerCase();
  if (lower.includes('campaign') || lower.includes('paused')) return AI_RESPONSES.campaign;
  if (lower.includes('gmail') || lower.includes('sync') || lower.includes('email sync')) return AI_RESPONSES.gmail;
  if (lower.includes('import') || lower.includes('csv')) return AI_RESPONSES.import;
  if (lower.includes('open rate') || lower.includes('deliverability')) return AI_RESPONSES.open;
  return AI_RESPONSES.default;
}

// ─── Small helpers ────────────────────────────────────────────────────────────

function GlowChip({ label, color }: { label: string; color: string }) {
  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, px: 1, py: 0.25,
      borderRadius: '999px', border: `1px solid ${alpha(color, 0.35)}`,
      bgcolor: alpha(color, 0.1), }}>
      <FiberManualRecordRoundedIcon sx={{ fontSize: 8, color }} />
      <Typography sx={{ fontSize: 11, fontWeight: 600, color, lineHeight: 1 }}>{label}</Typography>
    </Box>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  const theme = useTheme();
  return (
    <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em',
      textTransform: 'uppercase', color: theme.palette.text.disabled, mb: 1.5 }}>
      {children}
    </Typography>
  );
}

function ThinDivider() {
  const theme = useTheme();
  return <Box sx={{ height: '1px', bgcolor: theme.palette.divider, my: 2 }} />;
}

// ─── AI Panel ─────────────────────────────────────────────────────────────────

interface ChatMsg { role: 'user' | 'ai'; text: string; }

function AIPanel() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const gradients = isDark ? darkGradients : lightGradients;
  const [messages, setMessages] = useState<ChatMsg[]>([
    { role: 'ai', text: 'Hi! I\'m your Proxipilot assistant. Ask me anything about campaigns, email sync, or lead imports.' },
  ]);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [messages, typing]);

  function send(text: string) {
    if (!text.trim()) return;
    setMessages(prev => [...prev, { role: 'user', text }]);
    setInput('');
    setTyping(true);
    setTimeout(() => {
      setTyping(false);
      setMessages(prev => [...prev, { role: 'ai', text: getAIResponse(text) }]);
    }, 1200);
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 420, width: '100%', boxSizing: 'border-box',
      border: `1px solid ${theme.palette.divider}`, borderRadius: 2,
      bgcolor: isDark ? alpha('#818cf8', 0.04) : alpha('#818cf8', 0.02), overflow: 'hidden' }}>
      {/* Header */}
      <Box sx={{ px: 2, py: 1.5, borderBottom: `1px solid ${theme.palette.divider}`,
        background: gradients.primary, display: 'flex', alignItems: 'center', gap: 1 }}>
        <AutoAwesomeRoundedIcon sx={{ fontSize: 18, color: '#fff' }} />
        <Typography sx={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>AI Assistant</Typography>
        <Box sx={{ ml: 'auto' }}><GlowChip label="Online" color="#34d399" /></Box>
      </Box>
      {/* Messages */}
      <Box ref={messagesRef} sx={{ flex: 1, overflowY: 'auto', px: 2, py: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
        {messages.map((m, i) => (
          <Box key={i} sx={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
            <Box sx={{ maxWidth: '80%', px: 1.5, py: 1, borderRadius: 2,
              bgcolor: m.role === 'user'
                ? alpha('#818cf8', isDark ? 0.3 : 0.15)
                : isDark ? alpha('#fff', 0.06) : alpha('#000', 0.04),
              border: `1px solid ${m.role === 'user' ? alpha('#818cf8', 0.3) : theme.palette.divider}` }}>
              <Typography sx={{ fontSize: 13, color: theme.palette.text.primary, lineHeight: 1.5 }}>
                {m.text}
              </Typography>
            </Box>
          </Box>
        ))}
        {typing && (
          <Box sx={{ display: 'flex', gap: 0.5, px: 1.5, py: 1 }}>
            {[0, 1, 2].map(i => (
              <Box key={i} sx={{ width: 6, height: 6, borderRadius: '50%',
                bgcolor: alpha('#818cf8', 0.6),
                animation: 'bounce 1s infinite', animationDelay: `${i * 0.2}s`,
                '@keyframes bounce': { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-4px)' } } }} />
            ))}
          </Box>
        )}
        <div />
      </Box>
      {/* Quick prompts */}
      <Box sx={{ px: 2, pb: 1, display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
        {AI_QUICK_PROMPTS.map(p => (
          <Box key={p} onClick={() => send(p)} sx={{ px: 1.25, py: 0.5, borderRadius: '999px', cursor: 'pointer',
            border: `1px solid ${alpha('#818cf8', 0.35)}`, bgcolor: alpha('#818cf8', 0.08),
            transition: 'all 0.15s', '&:hover': { bgcolor: alpha('#818cf8', 0.18) } }}>
            <Typography sx={{ fontSize: 11, color: isDark ? '#a5b4fc' : '#4338ca', fontWeight: 500 }}>{p}</Typography>
          </Box>
        ))}
      </Box>
      {/* Input */}
      <Box sx={{ px: 2, pb: 1.5, display: 'flex', gap: 1, alignItems: 'center',
        borderTop: `1px solid ${theme.palette.divider}`, pt: 1 }}>
        <InputBase value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send(input)}
          placeholder="Ask anything…"
          sx={{ flex: 1, fontSize: 13, px: 1.5, py: 0.75, borderRadius: 1.5,
            border: `1px solid ${theme.palette.divider}`,
            bgcolor: isDark ? alpha('#fff', 0.04) : alpha('#000', 0.03),
            color: theme.palette.text.primary }} />
        <IconButton size="small" onClick={() => send(input)} disabled={!input.trim()}
          sx={{ bgcolor: alpha('#818cf8', 0.15), '&:hover': { bgcolor: alpha('#818cf8', 0.25) },
            '&:disabled': { opacity: 0.4 } }}>
          <SendRoundedIcon sx={{ fontSize: 16, color: '#818cf8' }} />
        </IconButton>
      </Box>
    </Box>
  );
}

// ─── Ticket Modal ─────────────────────────────────────────────────────────────

function TicketModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [sent, setSent] = useState(false);

  function handleSend() {
    if (!subject.trim() || !body.trim()) return;
    setSent(true);
  }

  function handleClose() {
    setSent(false);
    setSubject('');
    setBody('');
    onClose();
  }

  return (
    <Modal open={open} onClose={handleClose}>
      <Box sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        width: { xs: '90vw', sm: 480 }, borderRadius: 2.5, outline: 'none',
        bgcolor: theme.palette.background.paper, border: `1px solid ${theme.palette.divider}`,
        boxShadow: isDark ? '0 24px 64px rgba(0,0,0,0.6)' : '0 24px 64px rgba(0,0,0,0.15)',
        p: 3, animation: 'popIn 0.2s ease',
        '@keyframes popIn': { from: { opacity: 0, transform: 'translate(-50%,-48%) scale(0.96)' }, to: { opacity: 1, transform: 'translate(-50%,-50%) scale(1)' } } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2.5 }}>
          <Typography sx={{ fontWeight: 700, fontSize: 16 }}>Submit a Support Ticket</Typography>
          <IconButton size="small" onClick={handleClose}><CloseRoundedIcon sx={{ fontSize: 18 }} /></IconButton>
        </Box>
        {sent ? (
          <Box sx={{ textAlign: 'center', py: 3, animation: 'popIn 0.25s ease' }}>
            <CheckCircleRoundedIcon sx={{ fontSize: 48, color: '#34d399', mb: 1.5 }} />
            <Typography sx={{ fontWeight: 700, fontSize: 16, mb: 0.5 }}>Ticket submitted!</Typography>
            <Typography sx={{ fontSize: 13, color: theme.palette.text.secondary }}>
              We typically respond within 2–4 hours during business hours.
            </Typography>
          </Box>
        ) : (
          <>
            <Box sx={{ mb: 2 }}>
              <Typography sx={{ fontSize: 12, fontWeight: 600, mb: 0.75, color: theme.palette.text.secondary }}>Subject</Typography>
              <InputBase value={subject} onChange={e => setSubject(e.target.value)}
                placeholder="Brief description of your issue"
                fullWidth sx={{ px: 1.5, py: 1, borderRadius: 1.5, fontSize: 13,
                  border: `1px solid ${theme.palette.divider}`,
                  bgcolor: isDark ? alpha('#fff', 0.04) : alpha('#000', 0.03),
                  color: theme.palette.text.primary }} />
            </Box>
            <Box sx={{ mb: 2.5 }}>
              <Typography sx={{ fontSize: 12, fontWeight: 600, mb: 0.75, color: theme.palette.text.secondary }}>Details</Typography>
              <InputBase value={body} onChange={e => setBody(e.target.value)}
                placeholder="Describe the issue in detail…" multiline rows={4} fullWidth
                sx={{ px: 1.5, py: 1, borderRadius: 1.5, fontSize: 13, alignItems: 'flex-start',
                  border: `1px solid ${theme.palette.divider}`,
                  bgcolor: isDark ? alpha('#fff', 0.04) : alpha('#000', 0.03),
                  color: theme.palette.text.primary }} />
            </Box>
            <Box onClick={handleSend}
              sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1,
                py: 1.25, borderRadius: 1.5, cursor: subject.trim() && body.trim() ? 'pointer' : 'not-allowed',
                opacity: subject.trim() && body.trim() ? 1 : 0.45,
                background: 'linear-gradient(135deg, #818cf8 0%, #a78bfa 100%)',
                transition: 'opacity 0.15s', '&:hover': { opacity: subject.trim() && body.trim() ? 0.9 : 0.45 } }}>
              <SendRoundedIcon sx={{ fontSize: 16, color: '#fff' }} />
              <Typography sx={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>Send Ticket</Typography>
            </Box>
            <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'center' }}>
              <CheckCircleRoundedIcon sx={{ fontSize: 14, color: '#34d399' }} />
              <Typography sx={{ fontSize: 11, color: theme.palette.text.disabled }}>
                Encrypted · Avg. response 2–4 hrs · 98% satisfaction
              </Typography>
            </Box>
          </>
        )}
      </Box>
    </Modal>
  );
}

// ─── Main HelpPage ────────────────────────────────────────────────────────────

export default function HelpPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const gradients = isDark ? darkGradients : lightGradients;

  const [ticketOpen, setTicketOpen] = useState(false);

  return (
    <Box sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', minHeight: 0, width: '100%',
      '&::-webkit-scrollbar': { width: 4 },
      '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.2), borderRadius: 2 },
      bgcolor: theme.palette.background.default }}>
      <TicketModal open={ticketOpen} onClose={() => setTicketOpen(false)} />

      {/* ── Hero ── */}
      <Box sx={{ position: 'relative', overflow: 'hidden', width: '100%', boxSizing: 'border-box',
        px: { xs: 2, md: 4 }, py: { xs: 4, md: 7 },
        background: isDark
          ? `linear-gradient(135deg, #1e1b4b 0%, #0f172a 50%, #1e293b 100%)`
          : `linear-gradient(135deg, #eef2ff 0%, #f5f3ff 60%, #ede9fe 100%)`,
        animation: 'fadeIn 0.5s ease',
        '@keyframes fadeIn': { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } } }}>
        {/* Decorative orbs */}
        <Box sx={{ position: 'absolute', top: -60, right: -60, width: 280, height: 280, borderRadius: '50%',
          background: alpha('#818cf8', isDark ? 0.15 : 0.12), filter: 'blur(60px)', pointerEvents: 'none' }} />
        <Box sx={{ position: 'absolute', bottom: -40, left: '30%', width: 200, height: 200, borderRadius: '50%',
          background: alpha('#c084fc', isDark ? 0.12 : 0.1), filter: 'blur(50px)', pointerEvents: 'none' }} />
        <Box sx={{ position: 'relative', width: '100%', maxWidth: { xs: '100%', md: 640 }, mx: { xs: 0, md: 'auto' }, textAlign: 'center' }}>
          <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75, px: 1.5, py: 0.5, mb: 2,
            borderRadius: '999px', border: `1px solid ${alpha('#818cf8', 0.35)}`, bgcolor: alpha('#818cf8', 0.1) }}>
            <AutoAwesomeRoundedIcon sx={{ fontSize: 14, color: '#818cf8' }} />
            <Typography sx={{ fontSize: 12, fontWeight: 600, color: isDark ? '#a5b4fc' : '#4338ca' }}>
              Help & Support
            </Typography>
          </Box>
          <Typography variant="h4" sx={{ fontWeight: 800, mb: 1.5, fontSize: { xs: 26, md: 34 },
            background: gradients.primary, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            How can we help you?
          </Typography>
        </Box>
      </Box>

      {/* ── Content ── */}
      <Box sx={{ width: '100%', boxSizing: 'border-box', px: { xs: 2, sm: 3, md: 4 }, py: 4 }}>

        {/* ── Categories ── */}
        <SectionLabel>Browse by category</SectionLabel>
        <Box sx={{ display: 'grid', gap: 1.5,
          gridTemplateColumns: { xs: 'repeat(2,1fr)', sm: 'repeat(3,1fr)', md: 'repeat(6,1fr)' }, mb: 4 }}>
          {HELP_CATEGORIES.map(cat => {
            const Icon = CAT_ICONS[cat.id];
            return (
              <Box key={cat.id} sx={{ p: 2, borderRadius: 2, cursor: 'pointer', textAlign: 'center',
                border: `1px solid ${alpha(cat.color, 0.25)}`,
                bgcolor: alpha(cat.color, isDark ? 0.07 : 0.05),
                transition: 'all 0.18s',
                '&:hover': { transform: 'translateY(-2px)', bgcolor: alpha(cat.color, isDark ? 0.14 : 0.1),
                  borderColor: alpha(cat.color, 0.5), boxShadow: `0 4px 16px ${alpha(cat.color, 0.2)}` } }}>
                <Icon sx={{ fontSize: 26, color: cat.color, mb: 0.75 }} />
                <Typography sx={{ fontSize: 12, fontWeight: 700, color: theme.palette.text.primary, lineHeight: 1.3, mb: 0.5 }}>
                  {cat.label}
                </Typography>
                <Typography sx={{ fontSize: 11, color: theme.palette.text.disabled }}>
                  {cat.articles} articles
                </Typography>
              </Box>
            );
          })}
        </Box>

        <ThinDivider />

        {/* ── Two-column: Articles + AI ── */}
        <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', lg: '1fr 360px' }, mb: 4 }}>
          {/* Left: Articles + Videos */}
          <Box>
            <SectionLabel>Popular articles</SectionLabel>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {HELP_ARTICLES.filter(a => a.popular).map((art, i, arr) => (
                <Box key={art.id} sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 1.5, cursor: 'pointer',
                  borderBottom: i < arr.length - 1 ? `1px solid ${theme.palette.divider}` : 'none',
                  transition: 'all 0.15s', '&:hover': { transform: 'translateX(2px)' },
                  '&:hover .art-title': { color: isDark ? '#a5b4fc' : '#4338ca' } }}>
                  <ArticleRoundedIcon sx={{ fontSize: 18, color: theme.palette.text.disabled, flexShrink: 0 }} />
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography className="art-title" sx={{ fontSize: 13, fontWeight: 600,
                      color: theme.palette.text.primary, transition: 'color 0.15s',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {art.title}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.25 }}>
                      <TrendingUpRoundedIcon sx={{ fontSize: 12, color: theme.palette.text.disabled }} />
                      <Typography sx={{ fontSize: 11, color: theme.palette.text.disabled }}>
                        {art.reads.toLocaleString()} reads · {art.mins} min read
                      </Typography>
                    </Box>
                  </Box>
                  {art.popular && <Box sx={{ display: { xs: 'none', sm: 'flex' } }}><GlowChip label="Popular" color="#818cf8" /></Box>}
                  <ChevronRightRoundedIcon sx={{ fontSize: 16, color: theme.palette.text.disabled, flexShrink: 0 }} />
                </Box>
              ))}
            </Box>

            <ThinDivider />

            <SectionLabel>Video tutorials</SectionLabel>
            <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr 1fr', sm: 'repeat(4,1fr)' } }}>
              {VIDEO_TUTORIALS.map((v, i) => (
                <Box key={i} sx={{ borderRadius: 2, overflow: 'hidden', cursor: 'pointer', minWidth: 0,
                  border: `1px solid ${theme.palette.divider}`,
                  transition: 'all 0.18s', '&:hover': { transform: 'translateY(-2px)',
                    boxShadow: `0 6px 20px ${alpha(v.color, 0.25)}` } }}>
                  <Box sx={{ height: 72, bgcolor: alpha(v.color, isDark ? 0.2 : 0.12),
                    display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <PlayCircleRoundedIcon sx={{ fontSize: 32, color: v.color }} />
                  </Box>
                  <Box sx={{ p: 1.25 }}>
                    <Typography sx={{ fontSize: 11, fontWeight: 600, color: theme.palette.text.primary,
                      lineHeight: 1.4, mb: 0.5 }}>{v.title}</Typography>
                    <Typography sx={{ fontSize: 11, color: theme.palette.text.disabled }}>{v.dur}</Typography>
                  </Box>
                </Box>
              ))}
            </Box>
          </Box>

          {/* Right: AI Panel */}
          <Box>
            <SectionLabel>AI Assistant</SectionLabel>
            <AIPanel />
          </Box>
        </Box>

        <ThinDivider />

        {/* ── Three-column bottom ── */}
        <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: 'repeat(3,1fr)' } }}>

          {/* My Tickets */}
          <Box>
            <SectionLabel>My tickets</SectionLabel>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {HELP_TICKETS.map((t, i) => (
                <Box key={t.id} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5, py: 1.5, cursor: 'pointer',
                  borderBottom: i < HELP_TICKETS.length - 1 ? `1px solid ${theme.palette.divider}` : 'none',
                  transition: 'all 0.15s', '&:hover': { transform: 'translateX(2px)' } }}>
                  <ConfirmationNumberRoundedIcon sx={{ fontSize: 16, color: t.color, mt: 0.25, flexShrink: 0 }} />
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography sx={{ fontSize: 13, fontWeight: 600, color: theme.palette.text.primary,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {t.subject}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                      <GlowChip label={t.status} color={t.color} />
                      <Typography sx={{ fontSize: 11, color: theme.palette.text.disabled }}>{t.time}</Typography>
                    </Box>
                  </Box>
                </Box>
              ))}
            </Box>
            <Box onClick={() => setTicketOpen(true)}
              sx={{ mt: 2, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1,
                py: 1, borderRadius: 1.5, cursor: 'pointer',
                border: `1px solid ${alpha('#818cf8', 0.35)}`, bgcolor: alpha('#818cf8', 0.07),
                transition: 'all 0.15s', '&:hover': { bgcolor: alpha('#818cf8', 0.14) } }}>
              <ConfirmationNumberRoundedIcon sx={{ fontSize: 15, color: '#818cf8' }} />
              <Typography sx={{ fontSize: 13, fontWeight: 600, color: isDark ? '#a5b4fc' : '#4338ca' }}>
                Submit new ticket
              </Typography>
            </Box>
          </Box>

          {/* System Status */}
          <Box>
            <SectionLabel>System status</SectionLabel>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {SYSTEM_STATUS.map((s, i) => (
                <Box key={s.label} sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 1.5,
                  borderBottom: i < SYSTEM_STATUS.length - 1 ? `1px solid ${theme.palette.divider}` : 'none' }}>
                  <FiberManualRecordRoundedIcon sx={{ fontSize: 10, flexShrink: 0,
                    color: s.status === 'operational' ? '#34d399' : '#fbbf24' }} />
                  <Typography sx={{ flex: 1, fontSize: 13, fontWeight: 600, color: theme.palette.text.primary }}>
                    {s.label}
                  </Typography>
                  <GlowChip label={s.status} color={s.status === 'operational' ? '#34d399' : '#fbbf24'} />
                  <Typography sx={{ fontSize: 11, color: theme.palette.text.disabled, minWidth: 48, textAlign: 'right' }}>
                    {s.uptime}
                  </Typography>
                </Box>
              ))}
            </Box>
            <Box sx={{ mt: 2, p: 1.5, borderRadius: 1.5, border: `1px solid ${theme.palette.divider}`,
              bgcolor: isDark ? alpha('#fff', 0.03) : alpha('#000', 0.02) }}>
              <Typography sx={{ fontSize: 12, color: theme.palette.text.secondary }}>
                All systems monitored 24/7. Subscribe to status updates at{' '}
                <Box component="span" sx={{ color: isDark ? '#a5b4fc' : '#4338ca', cursor: 'pointer',
                  '&:hover': { textDecoration: 'underline' } }}>
                  status.Proxipilot.com
                </Box>
              </Typography>
            </Box>
          </Box>

          {/* Contact options */}
          <Box>
            <SectionLabel>Contact support</SectionLabel>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {[
                { icon: ChatRoundedIcon, label: 'Live Chat', desc: 'Avg. wait < 2 min', color: '#818cf8', badge: 'Online' },
                { icon: EmailRoundedIcon, label: 'Email Support', desc: 'Reply within 4 hours', color: '#22d3ee', badge: null },
                { icon: ConfirmationNumberRoundedIcon, label: 'Submit Ticket', desc: 'Track your issue', color: '#c084fc', badge: null },
              ].map(opt => {
                const Icon = opt.icon;
                return (
                  <Box key={opt.label}
                    onClick={opt.label === 'Submit Ticket' ? () => setTicketOpen(true) : undefined}
                    sx={{ display: 'flex', alignItems: 'center', gap: 1.5, p: 1.5, borderRadius: 2, cursor: 'pointer',
                      border: `1px solid ${alpha(opt.color, 0.25)}`,
                      bgcolor: alpha(opt.color, isDark ? 0.07 : 0.05),
                      transition: 'all 0.18s',
                      '&:hover': { transform: 'translateX(2px)', bgcolor: alpha(opt.color, isDark ? 0.14 : 0.1),
                        borderColor: alpha(opt.color, 0.5) } }}>
                    <Box sx={{ width: 36, height: 36, borderRadius: 1.5, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', bgcolor: alpha(opt.color, 0.15), flexShrink: 0 }}>
                      <Icon sx={{ fontSize: 18, color: opt.color }} />
                    </Box>
                    <Box sx={{ flex: 1 }}>
                      <Typography sx={{ fontSize: 13, fontWeight: 700, color: theme.palette.text.primary }}>
                        {opt.label}
                      </Typography>
                      <Typography sx={{ fontSize: 11, color: theme.palette.text.disabled }}>{opt.desc}</Typography>
                    </Box>
                    {opt.badge && <GlowChip label={opt.badge} color={opt.color} />}
                    <ChevronRightRoundedIcon sx={{ fontSize: 16, color: theme.palette.text.disabled }} />
                  </Box>
                );
              })}
            </Box>
          </Box>

        </Box>
      </Box>
    </Box>
  );
}
