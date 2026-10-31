/** Highest score one visit can reach. */
export const MAX_VISIT = 180;

/** Visits per score from 0 to 180, from the statistics' counts keyed by score. */
export function visitCounts(visitScores: Readonly<Record<string, number>>): number[] {
  return Array.from({ length: MAX_VISIT + 1 }, (_, score) => visitScores[score] ?? 0);
}

/** All unbusted visits, misses included. */
export function visitTotal(visitScores: Readonly<Record<string, number>>): number {
  return Object.values(visitScores).reduce((sum, count) => sum + count, 0);
}

/** Each score's share of all visits in percent, from 0 to 180. */
export function visitShares(visitScores: Readonly<Record<string, number>>): number[] {
  const total = visitTotal(visitScores);
  return visitCounts(visitScores).map((count) => (total === 0 ? 0 : (count / total) * 100));
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
