/** A located tip, or a cell of them: `[x, y]` in board millimetres and how many tips it holds. */
export type TipPoint = readonly [x: number, y: number, count?: number];

/** Tips smoothed into a square grid centred on the bullseye. */
export interface TipDensity {
  /** Cells per side. */
  readonly size: number;
  /** Density per cell as a share of the densest one, row by row from the top left. */
  readonly shares: Float32Array;
  /** Tips per cm² in the densest cell. */
  readonly peak: number;
  /** Tips within `extent` of the bullseye, and beyond it. */
  readonly inside: number;
  readonly outside: number;
}

/**
 * Counts the tips within `extent` mm of the bullseye into `cell`-mm cells and spreads
 * each with a Gaussian of `sigma` mm. Cells beyond `extent` stay empty.
 */
export function tipDensity(
  points: readonly TipPoint[],
  extent: number,
  cell: number,
  sigma: number,
): TipDensity {
  const size = Math.round((2 * extent) / cell);
  const counts = new Float32Array(size * size);
  let inside = 0;
  let outside = 0;

  for (const [x, y, count = 1] of points) {
    if (Math.hypot(x, y) > extent) {
      outside += count;
      continue;
    }
    const column = Math.min(size - 1, Math.floor((x + extent) / cell));
    const row = Math.min(size - 1, Math.floor((extent - y) / cell));
    counts[row * size + column] += count;
    inside += count;
  }

  const kernel = gaussian(sigma / cell);
  const shares = blur(blur(counts, size, kernel, 1, size), size, kernel, size, 1);

  const centre = size / 2;
  let densest = 0;
  for (let row = 0; row < size; row++) {
    for (let column = 0; column < size; column++) {
      const index = row * size + column;
      if (Math.hypot(column + 0.5 - centre, row + 0.5 - centre) > centre) {
        shares[index] = 0;
      }
      densest = Math.max(densest, shares[index]);
    }
  }
  if (densest > 0) {
    for (let index = 0; index < shares.length; index++) {
      shares[index] /= densest;
    }
  }

  return { size, shares, peak: (densest / (cell * cell)) * 100, inside, outside };
}

/** A normalised Gaussian kernel out to three standard deviations, `sigma` in cells. */
function gaussian(sigma: number): Float32Array {
  const radius = Math.ceil(3 * sigma);
  const kernel = new Float32Array(2 * radius + 1);
  let sum = 0;
  for (let offset = -radius; offset <= radius; offset++) {
    const weight = Math.exp(-(offset * offset) / (2 * sigma * sigma));
    kernel[offset + radius] = weight;
    sum += weight;
  }
  return kernel.map((weight) => weight / sum);
}

/**
 * One pass of a separable blur: `step` walks along a line, `stride` from one line to the next.
 * Cells past the grid's edge count as empty.
 */
function blur(
  source: Float32Array,
  size: number,
  kernel: Float32Array,
  step: number,
  stride: number,
): Float32Array {
  const radius = (kernel.length - 1) / 2;
  const target = new Float32Array(source.length);
  for (let line = 0; line < size; line++) {
    for (let position = 0; position < size; position++) {
      let sum = 0;
      const from = Math.max(0, position - radius);
      const to = Math.min(size - 1, position + radius);
      for (let other = from; other <= to; other++) {
        sum += source[line * stride + other * step] * kernel[other - position + radius];
      }
      target[line * stride + position * step] = sum;
    }
  }
  return target;
}
