'use client';

import { useEffect, useState, useRef } from 'react';
import { Box, Typography, useTheme, alpha } from '@mui/material';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';

const AI_MESSAGES = [
  { icon: CheckCircleRoundedIcon, color: '#34d399', text: 'Auto-replied to Mike Torres — partnership inquiry handled', time: '2m ago' },
  { icon: AutoAwesomeRoundedIcon, color: '#c084fc', text: 'Suggested reply for Sarah Anderson ready — 94% confidence', time: '5m ago' },
  { icon: BoltRoundedIcon,        color: '#fbbf24', text: 'Prioritized 3 high-urgency emails in your inbox', time: '12m ago' },
  { icon: AutoAwesomeRoundedIcon, color: '#818cf8', text: 'Draft ready for Priya Rajan — campaign follow-up', time: '18m ago' },
];

const TYPING_TEXT = 'Analyzing your inbox patterns and generating smart replies...';

export default function AIActivityPanel() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  const [typedText, setTypedText] = useState('');
  const [isTyping, setIsTyping] = useState(true);
  const cancelRef = useRef(false);

  useEffect(() => {
    cancelRef.current = false;
    let charIdx = 0;
    setTypedText('');
    setIsTyping(true);

    const typeInterval = setInterval(() => {
      if (cancelRef.current) return;
      if (charIdx < TYPING_TEXT.length) {
        setTypedText(TYPING_TEXT.slice(0, charIdx + 1));
        charIdx++;
      } else {
        clearInterval(typeInterval);
        setTimeout(() => { if (!cancelRef.current) setIsTyping(false); }, 1200);
      }
    }, 38);

    return () => { cancelRef.current = true; clearInterval(typeInterval); };
  }, []);

  return (
    <Box sx={{
      borderRadius: '14px',
      border: `1px solid ${isDark ? 'rgba(192,132,252,0.2)' : alpha('#8b5cf6', 0.15)}`,
      background: isDark ? 'rgba(88,28,135,0.15)' : alpha('#8b5cf6', 0.03),
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      backdropFilter: isDark ? 'blur(12px)' : 'none',
    }}>
      {/* Header */}
      <Box sx={{
        display: 'flex', alignItems: 'center', gap: 1,
        px: 2, py: 1.5,
        borderBottom: `1px solid ${isDark ? 'rgba(192,132,252,0.15)' : alpha('#8b5cf6', 0.1)}`,
        background: isDark ? 'rgba(192,132,252,0.08)' : alpha('#8b5cf6', 0.05),
      }}>
        <AutoAwesomeRoundedIcon sx={{
          fontSize: 15, color: isDark ? '#c084fc' : '#8b5cf6',
          animation: 'ai-spin 12s linear infinite',
          '@keyframes ai-spin': { from: { transform: 'rotate(0deg)' }, to: { transform: 'rotate(360deg)' } },
        }} />
        <Typography sx={{ fontSize: '0.82rem', fontWeight: 600, color: 'text.primary' }}>
          AI Activity
        </Typography>
        <Box sx={{
          ml: 'auto', display: 'flex', alignItems: 'center', gap: 0.5,
          px: 0.85, py: 0.3, borderRadius: '6px',
          background: alpha('#34d399', isDark ? 0.18 : 0.1),
          border: `1px solid ${alpha('#34d399', 0.3)}`,
        }}>
          <Box sx={{
            width: 5, height: 5, borderRadius: '50%', background: '#34d399',
            animation: 'ai-pulse 2.5s ease-in-out infinite',
            '@keyframes ai-pulse': { '0%,100%': { opacity: 0.5 }, '50%': { opacity: 1 } },
          }} />
          <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: '#34d399' }}>Live</Typography>
        </Box>
      </Box>

      {/* Typing bubble */}
      <Box sx={{ px: 2, pt: 1.5, pb: 1 }}>
        <Box sx={{
          p: 1.25, borderRadius: '10px',
          background: isDark ? 'rgba(129,140,248,0.1)' : alpha('#4338ca', 0.05),
          border: `1px solid ${isDark ? 'rgba(129,140,248,0.2)' : alpha('#4338ca', 0.12)}`,
          minHeight: 52,
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.5 }}>
            <AutoAwesomeRoundedIcon sx={{ fontSize: 11, color: isDark ? '#818cf8' : 'primary.main' }} />
            <Typography sx={{
              fontSize: '0.6rem', fontWeight: 700,
              color: isDark ? '#818cf8' : 'primary.main',
              textTransform: 'uppercase', letterSpacing: '0.07em',
            }}>
              AI Brain
            </Typography>
          </Box>
          <Typography sx={{ fontSize: '0.72rem', color: isDark ? 'rgba(255,255,255,0.65)' : 'text.secondary', lineHeight: 1.5 }}>
            {typedText}
            {isTyping && (
              <Box component="span" sx={{
                display: 'inline-block', width: '1.5px', height: 12,
                background: isDark ? '#818cf8' : theme.palette.primary.main,
                ml: 0.25, verticalAlign: 'middle',
                animation: 'blink 1s step-end infinite',
                '@keyframes blink': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0 } },
              }} />
            )}
          </Typography>
        </Box>
      </Box>

      {/* Activity list */}
      <Box sx={{ px: 2, pb: 1.5, display: 'flex', flexDirection: 'column', gap: 0.75 }}>
        {AI_MESSAGES.map((msg, i) => {
          const Icon = msg.icon;
          return (
            <Box
              key={i}
              sx={{
                display: 'flex', alignItems: 'flex-start', gap: 1,
                p: 1, borderRadius: '8px',
                background: alpha(msg.color, isDark ? 0.08 : 0.05),
                border: `1px solid ${alpha(msg.color, isDark ? 0.2 : 0.12)}`,
              }}
            >
              <Box sx={{
                width: 22, height: 22, borderRadius: '6px', flexShrink: 0,
                background: alpha(msg.color, isDark ? 0.22 : 0.12),
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon sx={{ fontSize: 11, color: msg.color }} />
              </Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ fontSize: '0.7rem', color: isDark ? 'rgba(255,255,255,0.7)' : 'text.secondary', lineHeight: 1.4 }}>
                  {msg.text}
                </Typography>
                <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled', mt: 0.2 }}>
                  {msg.time}
                </Typography>
              </Box>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
