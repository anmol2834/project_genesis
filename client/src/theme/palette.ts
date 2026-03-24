// Design tokens — inspired by Linear/Vercel/Stripe aesthetic
export const brand = {
  50:  '#eef2ff',
  100: '#e0e7ff',
  200: '#c7d2fe',
  300: '#a5b4fc',
  400: '#818cf8',
  500: '#6366f1', // primary
  600: '#4f46e5',
  700: '#4338ca',
  800: '#3730a3',
  900: '#312e81',
} as const;

export const violet = {
  50:  '#f5f3ff',
  100: '#ede9fe',
  200: '#ddd6fe',
  300: '#c4b5fd',
  400: '#a78bfa',
  500: '#8b5cf6', // secondary
  600: '#7c3aed',
  700: '#6d28d9',
  800: '#5b21b6',
  900: '#4c1d95',
} as const;

export const neutral = {
  0:   '#ffffff',
  50:  '#f8fafc',
  100: '#f1f5f9',
  200: '#e2e8f0',
  300: '#cbd5e1',
  400: '#94a3b8',
  500: '#64748b',
  600: '#475569',
  700: '#334155',
  800: '#1e293b',
  850: '#172033',
  900: '#0f172a',
  950: '#080d18',
} as const;

export const semantic = {
  success: { main: '#10b981', light: '#34d399', dark: '#059669', contrastText: '#fff' },
  warning: { main: '#f59e0b', light: '#fbbf24', dark: '#d97706', contrastText: '#fff' },
  error:   { main: '#ef4444', light: '#f87171', dark: '#dc2626', contrastText: '#fff' },
  info:    { main: '#06b6d4', light: '#22d3ee', dark: '#0891b2', contrastText: '#fff' },
} as const;

export const gradients = {
  primary:   'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
  secondary: 'linear-gradient(135deg, #8b5cf6 0%, #a78bfa 100%)',
  aurora:    'linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)',
  sunset:    'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)',
  glass:     'linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%)',
} as const;
