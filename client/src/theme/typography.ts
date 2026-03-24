import type { TypographyVariantsOptions } from '@mui/material/styles';

export const typography: TypographyVariantsOptions = {
  fontFamily: '"Inter", "Inter Fallback", system-ui, -apple-system, sans-serif',
  fontWeightLight:   300,
  fontWeightRegular: 400,
  fontWeightMedium:  500,
  fontWeightBold:    700,

  h1: { fontSize: 'clamp(2rem, 5vw, 3.5rem)',   fontWeight: 700, lineHeight: 1.15, letterSpacing: '-0.03em' },
  h2: { fontSize: 'clamp(1.6rem, 4vw, 2.5rem)', fontWeight: 700, lineHeight: 1.2,  letterSpacing: '-0.025em' },
  h3: { fontSize: 'clamp(1.3rem, 3vw, 2rem)',   fontWeight: 600, lineHeight: 1.25, letterSpacing: '-0.02em' },
  h4: { fontSize: 'clamp(1.1rem, 2.5vw, 1.5rem)', fontWeight: 600, lineHeight: 1.3, letterSpacing: '-0.015em' },
  h5: { fontSize: '1.25rem', fontWeight: 600, lineHeight: 1.4, letterSpacing: '-0.01em' },
  h6: { fontSize: '1.1rem',  fontWeight: 600, lineHeight: 1.4, letterSpacing: '-0.01em' },

  subtitle1: { fontSize: '1rem',    fontWeight: 500, lineHeight: 1.6, letterSpacing: '-0.005em' },
  subtitle2: { fontSize: '0.875rem', fontWeight: 500, lineHeight: 1.6 },

  body1: { fontSize: '1rem',    fontWeight: 400, lineHeight: 1.7, letterSpacing: '-0.005em' },
  body2: { fontSize: '0.875rem', fontWeight: 400, lineHeight: 1.65 },

  button:  { fontSize: '0.875rem', fontWeight: 600, letterSpacing: '0.01em', textTransform: 'none' },
  caption: { fontSize: '0.75rem',  fontWeight: 400, lineHeight: 1.5, letterSpacing: '0.01em' },
  overline:{ fontSize: '0.7rem',   fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' },
};
