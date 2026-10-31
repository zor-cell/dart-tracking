/** A colour as red, green, blue and alpha, each 0 to 255. */
export type Rgba = readonly [number, number, number, number];

/** Share of the densest spot below which the cloud stays transparent by default. */
export const HEAT_CUTOFF = 0.04;

const TRANSPARENT: Rgba = [160, 230, 255, 0];

/** From sparse to densest: light blue through violet and red to yellow, ever more opaque.
 * Positions are on the square-root scale `heatColor` maps a share to; the cutoff comes first. */
const STOPS: readonly (readonly [at: number, color: Rgba])[] = [
  [0.28, [90, 180, 240, 77]],
  [0.45, [60, 90, 200, 105]],
  [0.6, [110, 40, 150, 175]],
  [0.75, [200, 30, 80, 200]],
  [0.88, [245, 110, 40, 215]],
  [1, [255, 220, 60, 240]],
];

/** The colour for a share of the densest spot, transparent below `cutoff`; the square root
 * keeps sparse areas visible. */
export function heatColor(share: number, cutoff = HEAT_CUTOFF): Rgba {
  const position = Math.sqrt(Math.min(1, Math.max(0, share)));
  const stops = [[Math.sqrt(cutoff), TRANSPARENT] as const, ...STOPS];
  const upper = stops.findIndex(([at]) => at >= position);
  if (upper <= 0) {
    return TRANSPARENT;
  }
  const [fromAt, from] = stops[upper - 1];
  const [toAt, to] = stops[upper];
  const blend = (position - fromAt) / (toAt - fromAt);
  const mix = (channel: number): number => from[channel] + (to[channel] - from[channel]) * blend;
  return [mix(0), mix(1), mix(2), mix(3)];
}

export function cssColor([red, green, blue, alpha]: Rgba): string {
  return `rgb(${Math.round(red)} ${Math.round(green)} ${Math.round(blue)} / ${(alpha / 255).toFixed(2)})`;
}
