import type { ThemeOptions } from '@mui/material/styles';
import { brand, violet, neutral, semantic } from './palette';
import { typography } from './typography';
import { darkShadows } from './shadows';
import { breakpoints } from './breakpoints';
import { spacingUnit } from './spacing';
import { shape } from './shape';

export const darkThemeOptions: ThemeOptions = {
  palette: {
    mode: 'dark',
    primary: {
      main:         brand[400],
      light:        brand[300],
      dark:         brand[600],
      contrastText: '#ffffff',
    },
    secondary: {
      main:         violet[400],
      light:        violet[300],
      dark:         violet[600],
      contrastText: '#ffffff',
    },
    success: { ...semantic.success, main: '#34d399' },
    warning: { ...semantic.warning, main: '#fbbf24' },
    error:   { ...semantic.error,   main: '#f87171' },
    info:    { ...semantic.info,    main: '#22d3ee' },
    background: {
      default: neutral[900],   // #0f172a — deep navy, not pure black
      paper:   neutral[800],   // #1e293b
    },
    text: {
      primary:   neutral[50],
      secondary: neutral[400],
      disabled:  neutral[600],
    },
    divider: 'rgba(148,163,184,0.12)',
    action: {
      hover:           'rgba(99,102,241,0.08)',
      selected:        'rgba(99,102,241,0.15)',
      disabledBackground: neutral[800],
    },
  },
  typography,
  shadows: darkShadows as never,
  breakpoints,
  spacing: spacingUnit,
  shape,
};
