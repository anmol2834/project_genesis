import type { ThemeOptions } from '@mui/material/styles';
import { brand, violet, neutral, semantic } from './palette';
import { typography } from './typography';
import { lightShadows } from './shadows';
import { breakpoints } from './breakpoints';
import { spacingUnit } from './spacing';
import { shape } from './shape';

export const lightThemeOptions: ThemeOptions = {
  palette: {
    mode: 'light',
    primary: {
      main:         brand[500],
      light:        brand[400],
      dark:         brand[700],
      contrastText: '#ffffff',
    },
    secondary: {
      main:         violet[500],
      light:        violet[400],
      dark:         violet[700],
      contrastText: '#ffffff',
    },
    success: semantic.success,
    warning: semantic.warning,
    error:   semantic.error,
    info:    semantic.info,
    background: {
      default: neutral[50],
      paper:   neutral[0],
    },
    text: {
      primary:   neutral[900],
      secondary: neutral[500],
      disabled:  neutral[300],
    },
    divider: neutral[200],
    action: {
      hover:           'rgba(99,102,241,0.04)',
      selected:        'rgba(99,102,241,0.08)',
      disabledBackground: neutral[100],
    },
  },
  typography,
  shadows: lightShadows as never,
  breakpoints,
  spacing: spacingUnit,
  shape,
};
