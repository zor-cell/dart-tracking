/** Where a value axis starts and ends. */
export interface AxisBounds {
  readonly min: number;
  readonly max: number;
}

/** Percentage points a percent axis reaches beyond the values, and the least step it rounds to. */
const PERCENT_MARGIN = 5;
const PERCENT_STEP = 10;
/** Share of the values' span another axis reaches beyond them, and the ticks it aims at. */
const MARGIN_SHARE = 0.1;
const TICKS = 4;

/** Bounds a little beyond the values on round steps, never below 0; a percent axis also
 * stays at or under 100. Null without a value. */
export function axisBounds(values: readonly (number | null)[], percent: boolean): AxisBounds | null {
  const known = values.filter((value): value is number => value !== null && Number.isFinite(value));
  if (known.length === 0) {
    return null;
  }
  const low = Math.min(...known);
  const high = Math.max(...known);
  if (percent) {
    const step = Math.max(PERCENT_STEP, niceStep((high - low + 2 * PERCENT_MARGIN) / TICKS));
    return {
      min: Math.max(0, roundDown(low - PERCENT_MARGIN, step)),
      max: Math.min(100, roundUp(high + PERCENT_MARGIN, step)),
    };
  }
  const margin = (high - low || Math.abs(high) || 1) * MARGIN_SHARE;
  const step = niceStep((high - low + 2 * margin) / TICKS);
  return { min: Math.max(0, roundDown(low - margin, step)), max: roundUp(high + margin, step) };
}

/** The round number nearest above `raw`: 1, 2, 2.5 or 5 times a power of ten. */
function niceStep(raw: number): number {
  const power = 10 ** Math.floor(Math.log10(raw));
  const nice = [1, 2, 2.5, 5, 10].find((factor) => raw <= factor * power) ?? 10;
  return nice * power;
}

function roundDown(value: number, step: number): number {
  return Number((Math.floor(value / step) * step).toFixed(6));
}

function roundUp(value: number, step: number): number {
  return Number((Math.ceil(value / step) * step).toFixed(6));
}

/** Pixels a game's dot may reach past the drawing area, and the room kept around it,
 * so a dot on a bound shows whole. */
export const DOT_ROOM = 4;
