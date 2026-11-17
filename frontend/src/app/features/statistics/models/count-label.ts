import { formatNumber } from '@angular/common';

/** "18 Spiele, 364 Darts", the line under a section of figures saying what it counts. */
export function gamesAndDarts(games: number, darts: number, locale: string): string {
  const count = formatNumber(darts, locale);
  return games === 1
    ? $localize`:@@stats.section.oneGame:1 Spiel, ${count}:darts: Darts`
    : $localize`:@@stats.section.games:${games}:games: Spiele, ${count}:darts: Darts`;
}
