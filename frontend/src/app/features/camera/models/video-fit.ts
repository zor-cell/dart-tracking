export interface FitRect {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

/** Where a frame lands inside a box under `object-fit: contain`: scaled to fit
 * whole, centred, letterboxed on the other axis. */
export function containRect(
  boxWidth: number,
  boxHeight: number,
  frameWidth: number,
  frameHeight: number,
): FitRect {
  const scale = Math.min(boxWidth / frameWidth, boxHeight / frameHeight);
  const width = frameWidth * scale;
  const height = frameHeight * scale;
  return { x: (boxWidth - width) / 2, y: (boxHeight - height) / 2, width, height };
}
