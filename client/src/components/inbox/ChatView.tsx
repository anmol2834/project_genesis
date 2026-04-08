'use client';

import { useState, useEffect, useRef } from 'react';
import { Box, Typography, useTheme, alpha, InputBase, IconButton, Tooltip, type Theme } from '@mui/material';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import MoreVertRoundedIcon from '@mui/icons-material/MoreVertRounded';
import DoneAllRoundedIcon from '@mui/icons-material/DoneAllRounded';
import DoneRoundedIcon from '@mui/icons-material/DoneRounded';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import AttachFileRoundedIcon from '@mui/icons-material/AttachFileRounded';
import EmojiEmotionsRoundedIcon from '@mui/icons-material/EmojiEmotionsRounded';
import FormatBoldRoundedIcon from '@mui/icons-material/FormatBoldRounded';
import LocalFireDepartmentRoundedIcon from '@mui/icons-material/LocalFireDepartmentRounded';
import { Conversation, Message, LeadTag } from './inboxData';
import { emailInboxApi } from '@/services/endpoints/emailInbox';
import { useAuth } from '@/contexts/AuthContext';

const LEAD_TAG_CONFIG: Record<LeadTag, { label: string; color: string; bg: string }> = {
  hot:  { label: 'Hot Lead',  color: '#ef4444', bg: 'rgba(239,68,68,0.12)'  },
  warm: { label: 'Warm Lead', color: '#f97316', bg: 'rgba(249,115,22,0.12)' },
  cold: { label: 'Cold Lead', color: '#60a5fa', bg: 'rgba(96,165,250,0.12)' },
};

// ── Typing indicator ──────────────────────────────────────────────────────────
function TypingIndicator({ isDark }: { isDark: boolean }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', px: 2, py: 0.75, mb: 0.5 }}>
      <Box sx={{
        display: 'inline-flex', alignItems: 'center', gap: 0.5,
        px: 1.25, py: 0.75,
        borderRadius: '14px 14px 14px 3px',
        background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(15,23,42,0.05)',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.08)'}`,
      }}>
        {[0, 1, 2].map((i) => (
          <Box key={i} sx={{
            width: 5, height: 5, borderRadius: '50%',
            background: isDark ? 'rgba(255,255,255,0.4)' : 'rgba(15,23,42,0.3)',
            animation: `typingBounce 1.3s ease-in-out ${i * 0.18}s infinite`,
            '@keyframes typingBounce': {
              '0%,60%,100%': { transform: 'translateY(0)', opacity: 0.4 },
              '30%': { transform: 'translateY(-5px)', opacity: 1 },
            },
          }} />
        ))}
      </Box>
    </Box>
  );
}

// ── Single message bubble ─────────────────────────────────────────────────────
function MessageBubble({ msg, isDark, theme }: {
  msg: Message;
  isDark: boolean;
  theme: Theme;
}) {
  const isSent = msg.role === 'sent';  // 'sent' = outgoing (right), 'received' = incoming (left)

  return (
    <Box sx={{
      display: 'flex',
      justifyContent: isSent ? 'flex-end' : 'flex-start',
      px: { xs: 1.5, sm: 2 },
      mb: 0.5,
      animation: 'msgIn 0.2s ease-out',
      '@keyframes msgIn': {
        from: { opacity: 0, transform: 'translateY(6px)' },
        to:   { opacity: 1, transform: 'translateY(0)' },
      },
    }}>
      <Box sx={{ maxWidth: { xs: '80%', sm: '65%' } }}>
        {/* Bubble */}
        <Box sx={{
          px: { xs: 1.25, sm: 1.5 },
          py: { xs: 0.85, sm: 1 },
          borderRadius: isSent ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
          background: isSent
            ? isDark
              ? 'linear-gradient(135deg, #4f46e5 0%, #818cf8 100%)'
              : 'linear-gradient(135deg, #4338ca 0%, #6366f1 100%)'
            : isDark
              ? 'rgba(255,255,255,0.07)'
              : alpha(theme.palette.text.primary, 0.05),
          border: isSent
            ? 'none'
            : `1px solid ${isDark ? 'rgba(255,255,255,0.09)' : theme.palette.divider}`,
          boxShadow: isSent
            ? '0 2px 14px rgba(99,102,241,0.28)'
            : isDark ? '0 1px 4px rgba(0,0,0,0.2)' : '0 1px 3px rgba(15,23,42,0.06)',
        }}>
          <Typography sx={{
            fontSize: { xs: '0.8rem', sm: '0.83rem' },
            color: isSent ? '#fff' : 'text.primary',
            lineHeight: 1.55,
            wordBreak: 'break-word',
          }}>
            {msg.text}
          </Typography>
        </Box>

        {/* Timestamp + read receipt */}
        <Box sx={{
          display: 'flex', alignItems: 'center', gap: 0.35,
          mt: 0.3, px: 0.5,
          justifyContent: isSent ? 'flex-end' : 'flex-start',
        }}>
          <Typography sx={{ fontSize: '0.57rem', color: 'text.disabled', lineHeight: 1 }}>
            {msg.time}
          </Typography>
          {isSent && msg.status === 'read' && (
            <DoneAllRoundedIcon sx={{ fontSize: 11, color: '#818cf8' }} />
          )}
          {isSent && msg.status === 'delivered' && (
            <DoneAllRoundedIcon sx={{ fontSize: 11, color: 'text.disabled' }} />
          )}
          {isSent && msg.status === 'sent' && (
            <DoneRoundedIcon sx={{ fontSize: 11, color: 'text.disabled' }} />
          )}
        </Box>
      </Box>
    </Box>
  );
}

// ── Date separator ────────────────────────────────────────────────────────────
function DateSeparator({ label, isDark }: { label: string; isDark: boolean }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 2, my: 1.5 }}>
      <Box sx={{ flex: 1, height: '1px', background: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(15,23,42,0.08)' }} />
      <Typography sx={{
        fontSize: '0.6rem', fontWeight: 600, color: 'text.disabled',
        textTransform: 'uppercase', letterSpacing: '0.08em', whiteSpace: 'nowrap',
      }}>
        {label}
      </Typography>
      <Box sx={{ flex: 1, height: '1px', background: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(15,23,42,0.08)' }} />
    </Box>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
interface Props {
  conversation: Conversation;
  onBack?: () => void;
}

export default function ChatView({ conversation, onBack }: Props) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [messages, setMessages] = useState<Message[]>(conversation.messages);
  const [input, setInput] = useState('');
  const [showTyping, setShowTyping] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);
  const [draft, setDraft] = useState<string | null>(conversation.draft ?? null);
  const [draftSending, setDraftSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const tagInfo = LEAD_TAG_CONFIG[conversation.leadTag];
  const { user } = useAuth();

  useEffect(() => {
    setMessages(conversation.messages);
    setShowTyping(false);
    setInput('');
    setDraft(conversation.draft ?? null);
  }, [conversation.id, conversation.messages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, showTyping]);

  const sendMessage = (text: string) => {
    if (!text.trim()) return;
    const newMsg: Message = {
      id: `m${Date.now()}`,
      role: 'sent',
      text: text.trim(),
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      status: 'sent',
    };
    setMessages((prev) => [...prev, newMsg]);
    setInput('');
    setShowTyping(true);
    setTimeout(() => setShowTyping(false), 2600);
  };

  const handleSendDraft = async () => {
    if (!conversation.draftMessageId || !user?.user_id) return;
    setDraftSending(true);
    try {
      // Find the email_account_id from the conversation messages
      const accountId = conversation.messages.find(m => m.message_id)?.message_id
        ? '' : '';  // will be resolved server-side via message_id lookup
      await emailInboxApi.sendDraft({
        message_id:       conversation.draftMessageId,
        user_id:          user.user_id,
        email_account_id: '',  // server resolves from message_id + user_id
      });
      if (draft) {
        sendMessage(draft);
      }
      setDraft(null);
    } catch (err) {
      console.error('[ChatView] Draft send failed:', err);
    } finally {
      setDraftSending(false);
    }
  };

  const canSend = input.trim().length > 0;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0 }}>

      {/* ── Header ── */}
      <Box sx={{
        display: 'flex', alignItems: 'center', gap: 1.5,
        px: { xs: 1.5, sm: 2 }, py: 1.25, flexShrink: 0,
        borderBottom: `1px solid ${theme.palette.divider}`,
        background: isDark ? 'rgba(8,13,24,0.85)' : theme.palette.background.paper,
        backdropFilter: 'blur(12px)',
      }}>
        {onBack && (
          <IconButton size="small" onClick={onBack}
            sx={{ color: 'text.secondary', display: { sm: 'none' }, mr: -0.5 }}>
            <ArrowBackRoundedIcon sx={{ fontSize: 18 }} />
          </IconButton>
        )}

        {/* Avatar */}
        <Box sx={{
          width: 38, height: 38, borderRadius: '50%', flexShrink: 0,
          background: alpha(conversation.avatarColor, isDark ? 0.2 : 0.1),
          border: `2px solid ${alpha(conversation.avatarColor, isDark ? 0.4 : 0.25)}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: conversation.avatarColor }}>
            {conversation.avatar}
          </Typography>
        </Box>

        {/* Info */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.15 }}>
            <Typography sx={{
              fontSize: '0.87rem', fontWeight: 700, color: 'text.primary',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {conversation.name}
            </Typography>
            <Box sx={{
              px: 0.65, py: 0.15, borderRadius: '5px', flexShrink: 0,
              background: tagInfo.bg,
              border: `1px solid ${alpha(tagInfo.color, 0.3)}`,
              display: 'flex', alignItems: 'center', gap: 0.3,
            }}>
              {conversation.leadTag === 'hot' && (
                <LocalFireDepartmentRoundedIcon sx={{ fontSize: 9, color: tagInfo.color }} />
              )}
              <Typography sx={{
                fontSize: '0.54rem', fontWeight: 700, color: tagInfo.color,
                textTransform: 'uppercase', letterSpacing: '0.06em',
              }}>
                {tagInfo.label}
              </Typography>
            </Box>
          </Box>
          <Typography sx={{
            fontSize: '0.67rem', color: 'text.disabled',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {conversation.subject} · {conversation.email}
          </Typography>
        </Box>

        {/* Actions */}
        <Box sx={{ display: 'flex', gap: 0.25, flexShrink: 0 }}>
          <Tooltip title="More" placement="bottom">
            <IconButton size="small" sx={{ color: 'text.secondary', width: 32, height: 32, borderRadius: '8px',
              '&:hover': { background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(15,23,42,0.05)' } }}>
              <MoreVertRoundedIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* ── Messages ── */}
      <Box sx={{
        flex: 1, overflowY: 'auto', py: 1,
        background: isDark
          ? 'radial-gradient(ellipse 80% 60% at 30% 40%, rgba(99,102,241,0.05) 0%, transparent 70%), #080d18'
          : 'radial-gradient(ellipse 80% 60% at 30% 40%, rgba(99,102,241,0.03) 0%, transparent 70%), #f8fafc',
        '&::-webkit-scrollbar': { width: 3 },
        '&::-webkit-scrollbar-thumb': { background: alpha(theme.palette.text.disabled, 0.18), borderRadius: 2 },
      }}>
        <DateSeparator label="Today" isDark={isDark} />
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} isDark={isDark} theme={theme} />
        ))}
        {showTyping && <TypingIndicator isDark={isDark} />}
        <div ref={bottomRef} />
      </Box>

      {/* ── Draft banner ── */}
      {draft && (
        <Box sx={{
          mx: { xs: 1.25, sm: 1.75 },
          mt: 1,
          borderRadius: '12px',
          border: `1.5px dashed ${isDark ? 'rgba(192,132,252,0.35)' : 'rgba(147,51,234,0.3)'}`,
          background: isDark ? 'rgba(192,132,252,0.07)' : 'rgba(147,51,234,0.04)',
          overflow: 'hidden',
          animation: 'draftIn 0.25s ease-out',
          '@keyframes draftIn': {
            from: { opacity: 0, transform: 'translateY(8px)' },
            to:   { opacity: 1, transform: 'translateY(0)' },
          },
        }}>
          {/* Label row */}
          <Box sx={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            px: 1.5, pt: 0.9, pb: 0.5,
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <AutoAwesomeRoundedIcon sx={{ fontSize: 11, color: '#c084fc' }} />
              <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: '#c084fc', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                AI Draft
              </Typography>
            </Box>
            {/* Dismiss */}
            <Box
              component="button"
              onClick={() => setDraft(null)}
              sx={{
                border: 'none', background: 'transparent', cursor: 'pointer', p: 0,
                fontSize: '0.6rem', color: 'text.disabled', lineHeight: 1,
                '&:hover': { color: 'text.secondary' },
              }}
            >
              ✕
            </Box>
          </Box>

          {/* Draft text */}
          <Typography sx={{
            px: 1.5, pb: 1,
            fontSize: { xs: '0.78rem', sm: '0.8rem' },
            color: 'text.primary',
            lineHeight: 1.55,
          }}>
            {draft}
          </Typography>

          {/* Action row */}
          <Box sx={{
            display: 'flex', gap: 1,
            px: 1.5, pb: 1.1,
          }}>
            <Box
              component="button"
              onClick={handleSendDraft}
              disabled={draftSending}
              sx={{
                flex: 1, border: 'none', cursor: draftSending ? 'not-allowed' : 'pointer',
                py: 0.65, borderRadius: '8px',
                background: isDark
                  ? 'linear-gradient(135deg, #7c3aed, #c084fc)'
                  : 'linear-gradient(135deg, #7c3aed, #a855f7)',
                color: '#fff',
                fontSize: '0.72rem', fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5,
                opacity: draftSending ? 0.7 : 1,
                transition: 'opacity 0.15s ease, transform 0.15s ease',
                '&:hover': { opacity: draftSending ? 0.7 : 0.9, transform: draftSending ? 'none' : 'scale(1.01)' },
                '&:active': { transform: 'scale(0.98)' },
              }}
            >
              <SendRoundedIcon sx={{ fontSize: 12 }} />
              {draftSending ? 'Sending…' : 'Yes, Send'}
            </Box>
            <Box
              component="button"
              onClick={() => { setInput(draft ?? ''); setDraft(null); }}
              sx={{
                px: 1.5, border: `1px solid ${isDark ? 'rgba(255,255,255,0.12)' : 'rgba(15,23,42,0.12)'}`,
                cursor: 'pointer', py: 0.65, borderRadius: '8px',
                background: 'transparent',
                color: 'text.secondary',
                fontSize: '0.72rem', fontWeight: 600,
                transition: 'background 0.15s ease',
                '&:hover': { background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(15,23,42,0.05)' },
              }}
            >
              Edit
            </Box>
          </Box>
        </Box>
      )}

      {/* ── Input area ── */}
      <Box sx={{
        px: { xs: 1.25, sm: 1.75 },
        pt: 1,
        pb: { xs: 1.25, sm: 1.5 },
        flexShrink: 0,
        borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : theme.palette.divider}`,
        background: isDark ? 'rgba(8,13,24,0.9)' : theme.palette.background.paper,
      }}>
        {/* Toolbar row */}
        <Box sx={{
          display: 'flex', alignItems: 'center', gap: 0.25,
          px: 0.5, pb: 0.75,
        }}>
          {[
            { icon: FormatBoldRoundedIcon, tip: 'Bold' },
            { icon: AttachFileRoundedIcon, tip: 'Attach file' },
            { icon: EmojiEmotionsRoundedIcon, tip: 'Emoji' },
          ].map(({ icon: Icon, tip }) => (
            <Tooltip key={tip} title={tip} placement="top">
              <IconButton size="small" sx={{
                width: 28, height: 28, borderRadius: '7px', color: 'text.disabled',
                '&:hover': {
                  color: 'text.secondary',
                  background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(15,23,42,0.05)',
                },
              }}>
                <Icon sx={{ fontSize: 15 }} />
              </IconButton>
            </Tooltip>
          ))}

          {/* AI badge — decorative, shows AI is active */}
          <Box sx={{
            ml: 'auto', display: 'flex', alignItems: 'center', gap: 0.4,
            px: 0.75, py: 0.3, borderRadius: '6px',
            background: alpha('#c084fc', isDark ? 0.12 : 0.07),
            border: `1px solid ${alpha('#c084fc', isDark ? 0.22 : 0.15)}`,
          }}>
            <AutoAwesomeRoundedIcon sx={{ fontSize: 9, color: '#c084fc' }} />
            <Typography sx={{ fontSize: '0.58rem', fontWeight: 600, color: '#c084fc' }}>
              AI Active
            </Typography>
          </Box>
        </Box>

        {/* Input box */}
        <Box sx={{
          display: 'flex', alignItems: 'flex-end', gap: 1,
          px: 1.5, py: 1,
          borderRadius: '14px',
          border: `1.5px solid ${
            inputFocused
              ? isDark ? 'rgba(129,140,248,0.55)' : alpha(theme.palette.primary.main, 0.5)
              : isDark ? 'rgba(255,255,255,0.1)' : alpha(theme.palette.text.primary, 0.12)
          }`,
          background: isDark
            ? inputFocused ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.03)'
            : inputFocused ? '#fff' : alpha(theme.palette.text.primary, 0.02),
          boxShadow: inputFocused
            ? isDark
              ? '0 0 0 3px rgba(129,140,248,0.12)'
              : `0 0 0 3px ${alpha(theme.palette.primary.main, 0.08)}`
            : 'none',
          transition: 'border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease',
        }}>
          <InputBase
            inputRef={inputRef}
            multiline
            maxRows={5}
            placeholder="Type a message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage(input);
              }
            }}
            sx={{
              flex: 1,
              fontSize: { xs: '0.82rem', sm: '0.85rem' },
              color: 'text.primary',
              lineHeight: 1.55,
              '& textarea': { padding: 0 },
              '& textarea::placeholder': { color: theme.palette.text.disabled, opacity: 1 },
            }}
          />

          {/* Send button */}
          <IconButton
            size="small"
            onClick={() => sendMessage(input)}
            disabled={!canSend}
            sx={{
              width: 34, height: 34, borderRadius: '10px', flexShrink: 0,
              background: canSend
                ? isDark
                  ? 'linear-gradient(135deg, #4f46e5, #818cf8)'
                  : 'linear-gradient(135deg, #4338ca, #6366f1)'
                : isDark ? 'rgba(255,255,255,0.05)' : alpha(theme.palette.text.primary, 0.05),
              color: canSend ? '#fff' : 'text.disabled',
              transition: 'all 0.2s ease',
              '&:hover': {
                transform: canSend ? 'scale(1.06)' : 'none',
                boxShadow: canSend ? '0 4px 14px rgba(99,102,241,0.4)' : 'none',
              },
              '&:active': { transform: 'scale(0.97)' },
              '&.Mui-disabled': {
                background: isDark ? 'rgba(255,255,255,0.04)' : alpha(theme.palette.text.primary, 0.04),
                color: theme.palette.text.disabled,
              },
            }}
          >
            <SendRoundedIcon sx={{ fontSize: 15 }} />
          </IconButton>
        </Box>

        {/* Hint */}
        <Typography sx={{
          fontSize: '0.57rem', color: 'text.disabled',
          mt: 0.6, px: 0.5,
          display: { xs: 'none', sm: 'block' },
        }}>
          Enter to send · Shift+Enter for new line
        </Typography>
      </Box>
    </Box>
  );
}
