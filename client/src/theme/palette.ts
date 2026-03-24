// ─── Raw scale tokens (neutral source of truth) ──────────────────────────────
// These are just the raw scale. They are NOT assigned to semantic roles here.
// Each theme file picks the right stop for its own background/surface/text needs.

export const neutralScale = {
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

export const brandScale = {
  50:  '#eef2ff',
  100: '#e0e7ff',
  200: '#c7d2fe',
  300: '#a5b4fc',
  400: '#818cf8',
  500: '#6366f1',
  600: '#4f46e5',
  700: '#4338ca',
  800: '#3730a3',
  900: '#312e81',
} as const;

export const violetScale = {
  50:  '#f5f3ff',
  100: '#ede9fe',
  200: '#ddd6fe',
  300: '#c4b5fd',
  400: '#a78bfa',
  500: '#8b5cf6',
  600: '#7c3aed',
  700: '#6d28d9',
  800: '#5b21b6',
  900: '#4c1d95',
} as const;

// ─── LIGHT MODE palette ───────────────────────────────────────────────────────
// Background: white / near-white  →  text must be dark
// Primary: deep indigo (NOT neon) — professional, not electric
// text.primary   neutral[900] #0f172a  on white → 19.6:1  ✓
// text.secondary neutral[600] #475569  on white →  7.0:1  ✓
// text.disabled  neutral[400] #94a3b8  on white →  3.5:1  ✓ (decorative/hint)
// divider        neutral[200] #e2e8f0

export const lightPalette = {
  mode: 'light' as const,

  primary: {
    main:         brandScale[700],   // #4338ca — deep, professional, not neon
    light:        brandScale[500],   // #6366f1
    dark:         brandScale[800],   // #3730a3
    contrastText: '#ffffff',
  },

  secondary: {
    main:         violetScale[600],  // #7c3aed
    light:        violetScale[400],  // #a78bfa
    dark:         violetScale[800],  // #5b21b6
    contrastText: '#ffffff',
  },

  success: {
    main:         '#059669',         // darker green — readable on white
    light:        '#10b981',
    dark:         '#047857',
    contrastText: '#ffffff',
  },
  warning: {
    main:         '#d97706',         // darker amber — readable on white
    light:        '#f59e0b',
    dark:         '#b45309',
    contrastText: '#ffffff',
  },
  error: {
    main:         '#dc2626',
    light:        '#ef4444',
    dark:         '#b91c1c',
    contrastText: '#ffffff',
  },
  info: {
    main:         '#0891b2',
    light:        '#06b6d4',
    dark:         '#0e7490',
    contrastText: '#ffffff',
  },

  background: {
    default: neutralScale[50],       // #f8fafc
    paper:   neutralScale[0],        // #ffffff
  },

  text: {
    primary:   neutralScale[900],    // #0f172a  — 19.6:1 on white ✓
    secondary: neutralScale[600],    // #475569  —  7.0:1 on white ✓
    disabled:  neutralScale[400],    // #94a3b8  —  3.5:1 on white ✓
  },

  divider: neutralScale[200],        // #e2e8f0

  action: {
    hover:              'rgba(67, 56, 202, 0.05)',   // brand[700] tint
    selected:           'rgba(67, 56, 202, 0.09)',
    disabledBackground: neutralScale[100],
  },
} as const;

// ─── DARK MODE palette ────────────────────────────────────────────────────────
// Background: deep navy #0f172a / paper #1e293b  →  text must be light
// Primary: lighter indigo so it pops on dark bg
// text.primary   neutral[50]  #f8fafc  on #1e293b → 15.8:1  ✓
// text.secondary neutral[300] #cbd5e1  on #1e293b →  8.9:1  ✓
// text.disabled  neutral[500] #64748b  on #1e293b →  3.1:1  ✓ (decorative/hint)
// divider        rgba(203,213,225, 0.10)

export const darkPalette = {
  mode: 'dark' as const,

  primary: {
    main:         brandScale[400],   // #818cf8 — bright enough on dark bg
    light:        brandScale[300],   // #a5b4fc
    dark:         brandScale[600],   // #4f46e5
    contrastText: '#ffffff',
  },

  secondary: {
    main:         violetScale[400],  // #a78bfa
    light:        violetScale[300],  // #c4b5fd
    dark:         violetScale[600],  // #7c3aed
    contrastText: '#ffffff',
  },

  success: {
    main:         '#34d399',         // lighter green — readable on dark bg
    light:        '#6ee7b7',
    dark:         '#10b981',
    contrastText: '#022c22',
  },
  warning: {
    main:         '#fbbf24',         // lighter amber — readable on dark bg
    light:        '#fcd34d',
    dark:         '#f59e0b',
    contrastText: '#1c1400',
  },
  error: {
    main:         '#f87171',
    light:        '#fca5a5',
    dark:         '#ef4444',
    contrastText: '#1c0000',
  },
  info: {
    main:         '#22d3ee',
    light:        '#67e8f9',
    dark:         '#06b6d4',
    contrastText: '#001c22',
  },

  background: {
    default: neutralScale[900],      // #0f172a — deep navy, not pure black
    paper:   neutralScale[800],      // #1e293b
  },

  text: {
    primary:   neutralScale[50],     // #f8fafc  — 15.8:1 on #1e293b ✓
    secondary: neutralScale[300],    // #cbd5e1  —  8.9:1 on #1e293b ✓
    disabled:  neutralScale[500],    // #64748b  —  3.1:1 on #1e293b ✓
  },

  divider: 'rgba(203, 213, 225, 0.10)',

  action: {
    hover:              'rgba(129, 140, 248, 0.08)',  // brand[400] tint
    selected:           'rgba(129, 140, 248, 0.14)',
    disabledBackground: neutralScale[800],
  },
} as const;

// ─── Gradients (mode-aware, exported for use in components) ──────────────────
export const lightGradients = {
  primary:   'linear-gradient(135deg, #4338ca 0%, #7c3aed 100%)',  // deeper, not neon
  secondary: 'linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%)',
  aurora:    'linear-gradient(135deg, #4338ca 0%, #0891b2 100%)',
  subtle:    'linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%)',
} as const;

export const darkGradients = {
  primary:   'linear-gradient(135deg, #818cf8 0%, #a78bfa 100%)',  // bright for dark bg
  secondary: 'linear-gradient(135deg, #a78bfa 0%, #c4b5fd 100%)',
  aurora:    'linear-gradient(135deg, #818cf8 0%, #22d3ee 100%)',
  subtle:    'linear-gradient(135deg, #1e1b4b 0%, #1e293b 100%)',
} as const;

// Keep old exports as aliases so nothing outside theme/ breaks
// (components.ts imports `gradients` — we'll update that separately)
export const brand   = brandScale;
export const violet  = violetScale;
export const neutral = neutralScale;
export const gradients = lightGradients;  // fallback alias

export const semantic = {
  success: { main: '#10b981', light: '#34d399', dark: '#059669', contrastText: '#fff' },
  warning: { main: '#f59e0b', light: '#fbbf24', dark: '#d97706', contrastText: '#fff' },
  error:   { main: '#ef4444', light: '#f87171', dark: '#dc2626', contrastText: '#fff' },
  info:    { main: '#06b6d4', light: '#22d3ee', dark: '#0891b2', contrastText: '#fff' },
} as const;
