// Soft, layered shadows — not harsh, premium feel
export const lightShadows: string[] = [
  'none',
  '0px 1px 2px rgba(15, 23, 42, 0.06)',
  '0px 1px 3px rgba(15, 23, 42, 0.08), 0px 1px 2px rgba(15, 23, 42, 0.04)',
  '0px 4px 6px -1px rgba(15, 23, 42, 0.08), 0px 2px 4px -1px rgba(15, 23, 42, 0.04)',
  '0px 10px 15px -3px rgba(15, 23, 42, 0.08), 0px 4px 6px -2px rgba(15, 23, 42, 0.04)',
  '0px 20px 25px -5px rgba(15, 23, 42, 0.08), 0px 10px 10px -5px rgba(15, 23, 42, 0.03)',
  '0px 25px 50px -12px rgba(15, 23, 42, 0.12)',
  '0px 32px 64px -12px rgba(15, 23, 42, 0.14)',
  // brand-tinted shadow (for primary elements)
  '0px 8px 24px rgba(99, 102, 241, 0.18)',
  // glass shadow
  '0px 8px 32px rgba(15, 23, 42, 0.06), inset 0 1px 0 rgba(255,255,255,0.6)',
  ...Array(15).fill('none'),
];

export const darkShadows: string[] = [
  'none',
  '0px 1px 2px rgba(0, 0, 0, 0.3)',
  '0px 1px 3px rgba(0, 0, 0, 0.4), 0px 1px 2px rgba(0, 0, 0, 0.2)',
  '0px 4px 6px -1px rgba(0, 0, 0, 0.4), 0px 2px 4px -1px rgba(0, 0, 0, 0.2)',
  '0px 10px 15px -3px rgba(0, 0, 0, 0.4), 0px 4px 6px -2px rgba(0, 0, 0, 0.2)',
  '0px 20px 25px -5px rgba(0, 0, 0, 0.4), 0px 10px 10px -5px rgba(0, 0, 0, 0.15)',
  '0px 25px 50px -12px rgba(0, 0, 0, 0.5)',
  '0px 32px 64px -12px rgba(0, 0, 0, 0.6)',
  '0px 8px 24px rgba(99, 102, 241, 0.3)',
  '0px 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255,255,255,0.06)',
  ...Array(15).fill('none'),
];
