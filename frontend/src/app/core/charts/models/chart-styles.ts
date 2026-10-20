import type { ChartTheme } from './chart-plugins';
import { SERIES_COLORS } from './series-colors';

/** The tooltip box every chart draws: surface colours, muted title, theme font. */
export function tooltipStyle({ text, muted, surface, border, font }: ChartTheme) {
  return {
    backgroundColor: surface,
    borderColor: border,
    borderWidth: 1,
    titleColor: muted,
    bodyColor: text,
    titleFont: { family: font, size: 11, weight: 'normal' as const },
    bodyFont: { family: font, size: 12 },
    padding: 8,
  };
}

/** Small muted tick labels, as on every axis. */
export function axisTicks({ muted, font }: ChartTheme) {
  return { color: muted, font: { family: font, size: 10 } };
}

/** A small muted axis caption. */
export function axisTitle({ muted, font }: ChartTheme, text: string) {
  return { display: true, text, color: muted, font: { family: font, size: 10 } };
}

/**
 * A player's series colour, faded when another player is highlighted. The alphas
 * are hex suffixes, so each chart picks how strong its marks are.
 */
export function seriesColor(
  playerId: number,
  highlightId: number | null,
  alpha: { readonly shown: string; readonly faded: string },
): string {
  const base = SERIES_COLORS[playerId % SERIES_COLORS.length];
  return `${base}${highlightId === null || highlightId === playerId ? alpha.shown : alpha.faded}`;
}
