import type { ThemeOptions } from '@mui/material/styles';
import { darkPalette } from './palette';
import { typography } from './typography';
import { darkShadows } from './shadows';
import { breakpoints } from './breakpoints';
import { spacingUnit } from './spacing';
import { shape } from './shape';

export const darkThemeOptions: ThemeOptions = {
  palette: darkPalette,
  typography,
  shadows: darkShadows as never,
  breakpoints,
  spacing: spacingUnit,
  shape,
};
