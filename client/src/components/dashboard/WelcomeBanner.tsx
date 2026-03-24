'use client';

import { useEffect, useState, useRef } from 'react';
import { Box, Typography, Button, Chip } from '@mui/material';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';

const INSIGHTS = [
  'You received 12 replies today — 3 auto-handled by AI',
  'AI response rate is 94% this week',
  'Campaign "Q4 Outreach" has 8 new replies',
  'Predictive replies saved you ~2.4 hours today',
];

// ── Inline SVG illustration (email + AI + analytics scene) ──────────────────
function BannerIllustration() {
  return (
    <Box
      component="svg"
      viewBox="0 0 420 220"
      xmlns="http://www.w3.org/2000/svg"
      sx={{ width: '100%', height: '100%', display: 'block' }}
      aria-hidden="true"
    >
      {/* ── Background blobs ── */}
      <ellipse cx="320" cy="80" rx="110" ry="90" fill="rgba(255,255,255,0.07)" />
      <ellipse cx="380" cy="170" rx="70" ry="55" fill="rgba(255,255,255,0.05)" />

      {/* ── Laptop body ── */}
      <rect x="110" y="60" width="200" height="130" rx="10" fill="rgba(255,255,255,0.18)" />
      <rect x="118" y="68" width="184" height="112" rx="6" fill="rgba(30,41,100,0.55)" />
      {/* laptop base */}
      <rect x="90" y="190" width="240" height="10" rx="5" fill="rgba(255,255,255,0.22)" />
      <rect x="155" y="200" width="110" height="6" rx="3" fill="rgba(255,255,255,0.12)" />

      {/* ── Screen: bar chart ── */}
      <rect x="130" y="148" width="18" height="24" rx="3" fill="rgba(255,255,255,0.55)" />
      <rect x="154" y="136" width="18" height="36" rx="3" fill="rgba(255,255,255,0.75)" />
      <rect x="178" y="124" width="18" height="48" rx="3" fill="#fff" />
      <rect x="202" y="132" width="18" height="40" rx="3" fill="rgba(255,255,255,0.75)" />
      <rect x="226" y="118" width="18" height="54" rx="3" fill="#fff" />
      {/* trend line */}
      <polyline points="139,148 163,136 187,122 211,130 235,116" fill="none" stroke="rgba(255,255,255,0.9)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      {/* dots */}
      {[[139,148],[163,136],[187,122],[211,130],[235,116]].map(([cx,cy],i) => (
        <circle key={i} cx={cx} cy={cy} r="3" fill="#fff" />
      ))}
      {/* screen label */}
      <text x="140" y="88" fontSize="8" fill="rgba(255,255,255,0.5)" fontFamily="sans-serif">ANALYTICS</text>
      <rect x="130" y="92" width="60" height="4" rx="2" fill="rgba(255,255,255,0.2)" />
      <rect x="130" y="100" width="40" height="4" rx="2" fill="rgba(255,255,255,0.15)" />

      {/* ── Floating email card ── */}
      <rect x="20" y="50" width="90" height="60" rx="8" fill="rgba(255,255,255,0.18)" />
      <rect x="28" y="58" width="74" height="44" rx="4" fill="rgba(255,255,255,0.12)" />
      {/* envelope flap */}
      <polyline points="28,58 65,82 102,58" fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth="1.5" strokeLinejoin="round" />
      <line x1="28" y1="102" x2="65" y2="80" stroke="rgba(255,255,255,0.5)" strokeWidth="1.2" />
      <line x1="102" y1="102" x2="65" y2="80" stroke="rgba(255,255,255,0.5)" strokeWidth="1.2" />
      {/* card label */}
      <rect x="28" y="116" width="50" height="4" rx="2" fill="rgba(255,255,255,0.35)" />
      <rect x="28" y="124" width="35" height="3" rx="1.5" fill="rgba(255,255,255,0.2)" />

      {/* ── AI badge (top right of laptop) ── */}
      <rect x="290" y="48" width="72" height="36" rx="10" fill="rgba(255,255,255,0.2)" />
      <circle cx="306" cy="66" r="10" fill="rgba(255,255,255,0.3)" />
      {/* star/sparkle */}
      <text x="300" y="70" fontSize="11" fill="#fff" fontFamily="sans-serif">✦</text>
      <rect x="320" y="58" width="34" height="4" rx="2" fill="rgba(255,255,255,0.7)" />
      <rect x="320" y="66" width="24" height="3" rx="1.5" fill="rgba(255,255,255,0.45)" />

      {/* ── Rising arrow ── */}
      <line x1="340" y1="175" x2="400" y2="105" stroke="rgba(255,255,255,0.6)" strokeWidth="2.5" strokeLinecap="round" />
      <polyline points="390,100 400,105 395,116" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

      {/* ── Small floating stat pill ── */}
      <rect x="22" y="155" width="80" height="28" rx="8" fill="rgba(255,255,255,0.18)" />
      <text x="32" y="165" fontSize="7" fill="rgba(255,255,255,0.6)" fontFamily="sans-serif">AI REPLIES</text>
      <text x="32" y="177" fontSize="10" fontWeight="bold" fill="#fff" fontFamily="sans-serif">94%</text>

      {/* ── Gear icon (top center) ── */}
      <circle cx="270" cy="30" r="14" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="2" />
      <circle cx="270" cy="30" r="6" fill="rgba(255,255,255,0.2)" />
      {[0,45,90,135,180,225,270,315].map((deg, i) => {
        const rad = (deg * Math.PI) / 180;
        const x1 = 270 + 10 * Math.cos(rad);
        const y1 = 30 + 10 * Math.sin(rad);
        const x2 = 270 + 14 * Math.cos(rad);
        const y2 = 30 + 14 * Math.sin(rad);
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(255,255,255,0.3)" strokeWidth="2.5" strokeLinecap="round" />;
      })}

      {/* ── Cloud ── */}
      <ellipse cx="370" cy="38" rx="22" ry="13" fill="rgba(255,255,255,0.12)" />
      <ellipse cx="355" cy="42" rx="14" ry="10" fill="rgba(255,255,255,0.1)" />
      <ellipse cx="385" cy="42" rx="14" ry="10" fill="rgba(255,255,255,0.1)" />
    </Box>
  );
}

export default function WelcomeBanner() {
  const [insightIdx, setInsightIdx] = useState(0);
  const [visible, setVisible] = useState(true);
  const cancelRef = useRef(false);

  useEffect(() => {
    cancelRef.current = false;
    const interval = setInterval(() => {
      if (cancelRef.current) return;
      setVisible(false);
      setTimeout(() => {
        if (cancelRef.current) return;
        setInsightIdx(i => (i + 1) % INSIGHTS.length);
        setVisible(true);
      }, 280);
    }, 3500);
    return () => { cancelRef.current = true; clearInterval(interval); };
  }, []);

  return (
    <Box sx={{
      borderRadius: '16px',
      overflow: 'hidden',
      position: 'relative',
      background: 'linear-gradient(120deg, #1a56db 0%, #1e40af 35%, #0ea5e9 100%)',
      boxShadow: '0 8px 32px rgba(14,165,233,0.3)',
      display: 'flex',
      alignItems: 'stretch',
      minHeight: { xs: 160, sm: 180 },
    }}>
      {/* Subtle wave blob behind illustration */}
      <Box sx={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse 60% 80% at 80% 50%, rgba(255,255,255,0.08) 0%, transparent 70%)',
      }} />

      {/* ── Left: text content ── */}
      <Box sx={{
        flex: '0 0 auto',
        width: { xs: '100%', sm: '52%' },
        px: { xs: 2.5, sm: 3.5 },
        py: { xs: 2.5, sm: 3 },
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        gap: 1.5,
        position: 'relative',
        zIndex: 1,
      }}>
        {/* AI chip */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip
            icon={<AutoAwesomeRoundedIcon sx={{ fontSize: '10px !important', color: '#fff !important' }} />}
            label="AI Active & Learning"
            size="small"
            sx={{
              background: 'rgba(255,255,255,0.18)',
              border: '1px solid rgba(255,255,255,0.3)',
              color: '#fff', fontWeight: 600, fontSize: '0.62rem', height: 20,
              '& .MuiChip-label': { px: 0.6 },
            }}
          />
        </Box>

        {/* Headline */}
        <Box>
          <Typography sx={{
            fontSize: { xs: '0.65rem', sm: '0.68rem' },
            fontWeight: 600, color: 'rgba(255,255,255,0.6)',
            textTransform: 'uppercase', letterSpacing: '0.1em', mb: 0.4,
          }}>
            Good morning
          </Typography>
          <Typography sx={{
            fontSize: { xs: '1.25rem', sm: '1.5rem' },
            fontWeight: 800, color: '#fff',
            letterSpacing: '-0.025em', lineHeight: 1.15,
          }}>
            Welcome back, Alex 👋
          </Typography>
          {/* Rotating insight */}
          <Typography sx={{
            fontSize: '0.75rem', color: 'rgba(255,255,255,0.7)',
            mt: 0.5, lineHeight: 1.4,
            opacity: visible ? 1 : 0,
            transition: 'opacity 0.28s ease',
            minHeight: 20,
          }}>
            {INSIGHTS[insightIdx]}
          </Typography>
        </Box>

        {/* CTA button */}
        <Box>
          <Button
            size="small"
            endIcon={<ArrowForwardRoundedIcon sx={{ fontSize: '14px !important' }} />}
            sx={{
              background: 'rgba(255,255,255,0.18)',
              border: '1px solid rgba(255,255,255,0.35)',
              color: '#fff',
              fontWeight: 700,
              fontSize: '0.72rem',
              px: 2, py: 0.7,
              borderRadius: '8px',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              backdropFilter: 'blur(8px)',
              '&:hover': {
                background: 'rgba(255,255,255,0.28)',
                borderColor: 'rgba(255,255,255,0.5)',
              },
            }}
          >
            View Dashboard
          </Button>
        </Box>
      </Box>

      {/* ── Right: illustration ── */}
      <Box sx={{
        display: { xs: 'none', sm: 'flex' },
        flex: 1,
        alignItems: 'center',
        justifyContent: 'flex-end',
        pr: 1,
        position: 'relative',
        zIndex: 1,
        overflow: 'hidden',
      }}>
        <Box sx={{ width: '100%', maxWidth: 420, height: 200 }}>
          <BannerIllustration />
        </Box>
      </Box>
    </Box>
  );
}
