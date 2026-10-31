/** Highest score one visit can reach. */
export const MAX_VISIT = 180;

/** Visits per score from 0 to 180, from the statistics' counts keyed by score. */
export function visitCounts(visitScores: Readonly<Record<string, number>>): number[] {
  return Array.from({ length: MAX_VISIT + 1 }, (_, score) => visitScores[score] ?? 0);
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
