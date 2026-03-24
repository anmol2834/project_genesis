import type { Components, Theme } from '@mui/material/styles';
import { gradients } from './palette';

export const components = (theme: Theme): Components<Theme> => ({
  MuiCssBaseline: {
    styleOverrides: {
      '*, *::before, *::after': { boxSizing: 'border-box' },
      html: { scrollBehavior: 'smooth', WebkitFontSmoothing: 'antialiased', MozOsxFontSmoothing: 'grayscale' },
      body: { transition: 'background-color 0.2s ease, color 0.2s ease' },
      '::-webkit-scrollbar': { width: '6px', height: '6px' },
      '::-webkit-scrollbar-track': { background: 'transparent' },
      '::-webkit-scrollbar-thumb': { background: theme.palette.divider, borderRadius: '9999px' },
    },
  },

  MuiButton: {
    defaultProps: { disableElevation: true },
    styleOverrides: {
      root: {
        borderRadius: '10px',
        padding: '8px 20px',
        fontWeight: 600,
        transition: 'all 0.15s ease',
        '&:active': { transform: 'scale(0.98)' },
      },
      containedPrimary: {
        background: gradients.primary,
        '&:hover': { background: gradients.primary, filter: 'brightness(1.08)', boxShadow: theme.shadows[8] },
      },
      outlinedPrimary: {
        borderColor: theme.palette.primary.main,
        '&:hover': { background: theme.palette.action.hover },
      },
      sizeLarge:  { padding: '12px 28px', fontSize: '1rem' },
      sizeSmall:  { padding: '5px 14px', fontSize: '0.8125rem' },
    },
    variants: [
      {
        props: { variant: 'soft' as never },
        style: {
          background: theme.palette.mode === 'dark'
            ? 'rgba(99,102,241,0.15)'
            : 'rgba(99,102,241,0.08)',
          color: theme.palette.primary.main,
          '&:hover': {
            background: theme.palette.mode === 'dark'
              ? 'rgba(99,102,241,0.25)'
              : 'rgba(99,102,241,0.14)',
          },
        },
      },
      {
        props: { variant: 'gradient' as never },
        style: {
          background: gradients.aurora,
          color: '#fff',
          fontWeight: 600,
          '&:hover': { filter: 'brightness(1.1)', boxShadow: theme.shadows[8] },
        },
      },
    ],
  },

  MuiTextField: {
    defaultProps: { variant: 'outlined' },
    styleOverrides: {
      root: {
        '& .MuiOutlinedInput-root': {
          borderRadius: '10px',
          transition: 'box-shadow 0.15s ease',
          '&.Mui-focused': { boxShadow: `0 0 0 3px ${theme.palette.primary.main}22` },
        },
      },
    },
  },

  MuiCard: {
    defaultProps: { elevation: 0 },
    styleOverrides: {
      root: {
        borderRadius: '14px',
        border: `1px solid ${theme.palette.divider}`,
        backgroundImage: 'none',
        transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
        '&:hover': { boxShadow: theme.shadows[4] },
      },
    },
  },

  MuiDialog: {
    styleOverrides: {
      paper: {
        borderRadius: '20px',
        backgroundImage: 'none',
        border: `1px solid ${theme.palette.divider}`,
        boxShadow: theme.shadows[6],
      },
    },
  },

  MuiTooltip: {
    defaultProps: { arrow: true },
    styleOverrides: {
      tooltip: {
        borderRadius: '8px',
        fontSize: '0.75rem',
        fontWeight: 500,
        padding: '6px 12px',
        background: theme.palette.mode === 'dark' ? '#1e293b' : '#0f172a',
      },
      arrow: {
        color: theme.palette.mode === 'dark' ? '#1e293b' : '#0f172a',
      },
    },
  },

  MuiChip: {
    styleOverrides: {
      root: {
        borderRadius: '8px',
        fontWeight: 500,
        fontSize: '0.8125rem',
      },
    },
  },

  MuiAvatar: {
    styleOverrides: {
      root: {
        fontWeight: 600,
        fontSize: '0.875rem',
      },
    },
  },

  MuiPaper: {
    styleOverrides: {
      root: { backgroundImage: 'none' },
    },
  },

  MuiAppBar: {
    defaultProps: { elevation: 0 },
    styleOverrides: {
      root: {
        backgroundImage: 'none',
        borderBottom: `1px solid ${theme.palette.divider}`,
        backdropFilter: 'blur(12px)',
        background: theme.palette.mode === 'dark'
          ? 'rgba(15,23,42,0.8)'
          : 'rgba(255,255,255,0.8)',
      },
    },
  },

  MuiListItemButton: {
    styleOverrides: {
      root: {
        borderRadius: '8px',
        '&.Mui-selected': {
          background: theme.palette.mode === 'dark'
            ? 'rgba(99,102,241,0.15)'
            : 'rgba(99,102,241,0.08)',
          color: theme.palette.primary.main,
        },
      },
    },
  },
});
