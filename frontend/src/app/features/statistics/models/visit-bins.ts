/** How many points a bar of the visit distribution spans: ten, or every score alone. */
export type VisitBinWidth = 10 | 1;

export const VISIT_BIN_WIDTHS: readonly { label: string; value: VisitBinWidth }[] = [
  { label: '10er', value: 10 },
  { label: 'Einzeln', value: 1 },
];

/** One bar: the scores it spans, both inclusive, and its visits by score. */
export interface VisitBin {
  readonly from: number;
  readonly to: number;
  readonly scores: readonly { readonly score: number; readonly count: number }[];
  readonly total: number;
}

/** The visits by score, keyed as the statistics send them, in bars from 0 to 180; with bars of
 * ten, 180 still gets one of its own. */
export function visitBins(
  visitScores: Readonly<Record<string, number>>,
  width: VisitBinWidth,
): VisitBin[] {
  const bins = Array.from({ length: 180 / width + 1 }, (_, index) => index * width);
  return bins.map((from) => {
    const to = Math.min(180, from + width - 1);
    const scores = Object.entries(visitScores)
      .map(([score, count]) => ({ score: Number(score), count }))
      .filter(({ score }) => score >= from && score <= to)
      .sort((a, b) => b.count - a.count || b.score - a.score);
    return {
      from,
      to,
      scores,
      total: scores.reduce((sum, entry) => sum + entry.count, 0),
    };
  });
}

/** The scores thrown most often, misses left out, the higher one on a tie. */
export function topVisits(
  visitScores: Readonly<Record<string, number>>,
  count: number,
): { readonly score: number; readonly count: number }[] {
  return Object.entries(visitScores)
    .map(([score, times]) => ({ score: Number(score), count: times }))
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.count - a.count || b.score - a.score)
    .slice(0, count);
}
