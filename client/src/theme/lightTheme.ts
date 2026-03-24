import type { ThemeOptions } from '@mui/material/styles';
import { lightPalette } from './palette';
import { typography } from './typography';
import { lightShadows } from './shadows';
import { breakpoints } from './breakpoints';
import { spacingUnit } from './spacing';
import { shape } from './shape';

export const lightThemeOptions: ThemeOptions = {
  palette: lightPalette,
  typography,
  shadows: lightShadows as never,
  breakpoints,
  spacing: spacingUnit,
  shape,
};
