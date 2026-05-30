'use client';

import { Box, Typography, alpha, useTheme } from '@mui/material';
import Lottie from 'lottie-react';
import { useEffect, useState } from 'react';

interface LottieLoaderProps {
  message?: string;
  submessage?: string;
  fullPage?: boolean;
}

export default function LottieLoader({ 
  message = 'Loading your settings...', 
  submessage = 'This will only take a moment',
  fullPage = false 
}: LottieLoaderProps) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(timer);
  }, []);

  // Transparent butterfly animation with wing flapping
  const butterflyAnimation = {
    v: '5.7.4',
    fr: 30,
    ip: 0,
    op: 120,
    w: 200,
    h: 200,
    nm: 'Butterfly',
    ddd: 0,
    assets: [],
    layers: [
      {
        ddd: 0,
        ind: 1,
        ty: 4,
        nm: 'Left Wing',
        sr: 1,
        ks: {
          o: { a: 0, k: 90 },
          r: {
            a: 1,
            k: [
              { t: 0, s: [0], e: [-25] },
              { t: 15, s: [-25], e: [0] },
              { t: 30, s: [0], e: [-25] },
              { t: 45, s: [-25], e: [0] },
              { t: 60, s: [0], e: [-25] },
              { t: 75, s: [-25], e: [0] },
              { t: 90, s: [0], e: [-25] },
              { t: 105, s: [-25], e: [0] },
              { t: 120, s: [0] }
            ]
          },
          p: { a: 0, k: [100, 100, 0] },
          a: { a: 0, k: [0, 0, 0] },
          s: { a: 0, k: [100, 100, 100] }
        },
        ao: 0,
        shapes: [
          {
            ty: 'gr',
            it: [
              {
                ty: 'sh',
                ks: {
                  a: 0,
                  k: {
                    i: [[0, 0], [-15, -20], [-5, 15], [0, 0]],
                    o: [[0, 0], [15, 20], [5, -15], [0, 0]],
                    v: [[-40, 0], [-35, -30], [-10, -10], [0, 0]],
                    c: true
                  }
                }
              },
              {
                ty: 'fl',
                c: { a: 0, k: [0.51, 0.55, 0.97, 1] },
                o: { a: 0, k: 100 }
              },
              {
                ty: 'tr',
                p: { a: 0, k: [0, 0] },
                a: { a: 0, k: [0, 0] },
                s: { a: 0, k: [100, 100] },
                r: { a: 0, k: 0 },
                o: { a: 0, k: 100 }
              }
            ]
          }
        ],
        ip: 0,
        op: 120,
        st: 0
      },
      {
        ddd: 0,
        ind: 2,
        ty: 4,
        nm: 'Right Wing',
        sr: 1,
        ks: {
          o: { a: 0, k: 90 },
          r: {
            a: 1,
            k: [
              { t: 0, s: [0], e: [25] },
              { t: 15, s: [25], e: [0] },
              { t: 30, s: [0], e: [25] },
              { t: 45, s: [25], e: [0] },
              { t: 60, s: [0], e: [25] },
              { t: 75, s: [25], e: [0] },
              { t: 90, s: [0], e: [25] },
              { t: 105, s: [25], e: [0] },
              { t: 120, s: [0] }
            ]
          },
          p: { a: 0, k: [100, 100, 0] },
          a: { a: 0, k: [0, 0, 0] },
          s: { a: 0, k: [100, 100, 100] }
        },
        ao: 0,
        shapes: [
          {
            ty: 'gr',
            it: [
              {
                ty: 'sh',
                ks: {
                  a: 0,
                  k: {
                    i: [[0, 0], [15, -20], [5, 15], [0, 0]],
                    o: [[0, 0], [-15, 20], [-5, -15], [0, 0]],
                    v: [[40, 0], [35, -30], [10, -10], [0, 0]],
                    c: true
                  }
                }
              },
              {
                ty: 'fl',
                c: { a: 0, k: [0.8, 0.4, 0.98, 1] },
                o: { a: 0, k: 100 }
              },
              {
                ty: 'tr',
                p: { a: 0, k: [0, 0] },
                a: { a: 0, k: [0, 0] },
                s: { a: 0, k: [100, 100] },
                r: { a: 0, k: 0 },
                o: { a: 0, k: 100 }
              }
            ]
          }
        ],
        ip: 0,
        op: 120,
        st: 0
      },
      {
        ddd: 0,
        ind: 3,
        ty: 4,
        nm: 'Body',
        sr: 1,
        ks: {
          o: { a: 0, k: 100 },
          r: { a: 0, k: 0 },
          p: { a: 0, k: [100, 100, 0] },
          a: { a: 0, k: [0, 0, 0] },
          s: { a: 0, k: [100, 100, 100] }
        },
        ao: 0,
        shapes: [
          {
            ty: 'gr',
            it: [
              {
                ty: 'el',
                p: { a: 0, k: [0, 0] },
                s: { a: 0, k: [8, 30] }
              },
              {
                ty: 'fl',
                c: { a: 0, k: [0.2, 0.84, 0.62, 1] },
                o: { a: 0, k: 100 }
              },
              {
                ty: 'tr',
                p: { a: 0, k: [0, 0] },
                a: { a: 0, k: [0, 0] },
                s: { a: 0, k: [100, 100] },
                r: { a: 0, k: 0 },
                o: { a: 0, k: 100 }
              }
            ]
          }
        ],
        ip: 0,
        op: 120,
        st: 0
      }
    ]
  };

  // Butterfly positions for floating effect
  const butterflies = [
    { top: '10%', left: '15%', delay: 0, duration: 8, scale: 0.8 },
    { top: '25%', right: '20%', delay: 1, duration: 10, scale: 1 },
    { top: '45%', left: '10%', delay: 2, duration: 9, scale: 0.9 },
    { top: '60%', right: '15%', delay: 1.5, duration: 11, scale: 0.85 },
    { top: '75%', left: '25%', delay: 0.5, duration: 10, scale: 0.95 },
  ];

  const containerStyles = fullPage ? {
    position: 'fixed' as const,
    inset: 0,
    zIndex: 9999,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: isDark 
      ? 'rgba(8, 13, 24, 0.95)' 
      : 'rgba(248, 250, 252, 0.95)',
    backdropFilter: 'blur(20px)',
    opacity: visible ? 1 : 0,
    transition: 'opacity 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
    pointerEvents: 'none' as const,
  } : {
    position: 'absolute' as const,
    inset: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: isDark 
      ? 'rgba(8, 13, 24, 0.98)' 
      : 'rgba(248, 250, 252, 0.98)',
    backdropFilter: 'blur(16px)',
    opacity: visible ? 1 : 0,
    transition: 'opacity 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
    zIndex: 10,
    pointerEvents: 'none' as const,
  };

  return (
    <Box sx={containerStyles}>
      {/* Floating butterflies across the page */}
      {butterflies.map((butterfly, index) => (
        <Box
          key={index}
          sx={{
            position: 'absolute',
            ...('top' in butterfly ? { top: butterfly.top } : {}),
            ...('left' in butterfly ? { left: butterfly.left } : {}),
            ...('right' in butterfly ? { right: butterfly.right } : {}),
            width: { xs: 60, sm: 80, md: 100 },
            height: { xs: 60, sm: 80, md: 100 },
            opacity: visible ? 0.7 : 0,
            transform: `scale(${butterfly.scale})`,
            animation: `float ${butterfly.duration}s ease-in-out infinite`,
            animationDelay: `${butterfly.delay}s`,
            '@keyframes float': {
              '0%, 100%': {
                transform: `translateY(0) translateX(0) scale(${butterfly.scale})`,
              },
              '25%': {
                transform: `translateY(-20px) translateX(10px) scale(${butterfly.scale * 1.1})`,
              },
              '50%': {
                transform: `translateY(-10px) translateX(-15px) scale(${butterfly.scale})`,
              },
              '75%': {
                transform: `translateY(-25px) translateX(5px) scale(${butterfly.scale * 0.9})`,
              },
            },
            transition: 'opacity 0.6s ease-out',
            transitionDelay: `${butterfly.delay * 0.2}s`,
          }}
        >
          <Lottie
            animationData={butterflyAnimation}
            loop={true}
            style={{
              width: '100%',
              height: '100%',
            }}
            rendererSettings={{
              preserveAspectRatio: 'xMidYMid meet',
              progressiveLoad: false,
              hideOnTransparent: true,
            }}
          />
        </Box>
      ))}

      {/* Center message */}
      <Box sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 3,
        px: 3,
        zIndex: 1,
        transform: visible ? 'translateY(0)' : 'translateY(20px)',
        transition: 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
        pointerEvents: 'auto' as const,
      }}>
        <Box sx={{ textAlign: 'center', maxWidth: 400 }}>
          <Typography sx={{
            fontSize: { xs: '1rem', sm: '1.1rem' },
            fontWeight: 700,
            color: 'text.primary',
            mb: 0.75,
            letterSpacing: '-0.02em',
            background: isDark
              ? 'linear-gradient(135deg, #818cf8 0%, #c084fc 100%)'
              : 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}>
            {message}
          </Typography>
          
          <Typography sx={{
            fontSize: { xs: '0.8rem', sm: '0.85rem' },
            color: 'text.secondary',
            opacity: 0.8,
          }}>
            {submessage}
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {[0, 1, 2].map((i) => (
            <Box
              key={i}
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: isDark
                  ? 'linear-gradient(135deg, #818cf8 0%, #c084fc 100%)'
                  : 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
                animation: 'bounce 1.4s ease-in-out infinite',
                animationDelay: `${i * 0.2}s`,
                '@keyframes bounce': {
                  '0%, 80%, 100%': { 
                    transform: 'scale(0.8)',
                    opacity: 0.5,
                  },
                  '40%': { 
                    transform: 'scale(1.2)',
                    opacity: 1,
                  },
                },
              }}
            />
          ))}
        </Box>
      </Box>
    </Box>
  );
}
