import { createTheme } from '@mui/material/styles';
import { lightThemeOptions } from './lightTheme';
import { darkThemeOptions } from './darkTheme';
import { components } from './components';

export type ThemeMode = 'light' | 'dark';

export function buildTheme(mode: ThemeMode) {
  const base = createTheme(mode === 'dark' ? darkThemeOptions : lightThemeOptions);
  return createTheme(base, { components: components(base) });
}

export const lightTheme = buildTheme('light');
export const darkTheme  = buildTheme('dark');
