// 8px base grid — consistent spacing across the system
export const spacingUnit = 8;

// Named spacing tokens for semantic usage
export const space = {
  px:  '1px',
  0.5: '4px',
  1:   '8px',
  1.5: '12px',
  2:   '16px',
  3:   '24px',
  4:   '32px',
  5:   '40px',
  6:   '48px',
  8:   '64px',
  10:  '80px',
  12:  '96px',
  16:  '128px',
} as const;

// Container max-widths
export const containers = {
  sm:  '640px',
  md:  '768px',
  lg:  '1024px',
  xl:  '1280px',
  '2xl': '1440px',
} as const;
