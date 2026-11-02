/** A number of darts with its noun: "1 Dart", "3 Darts". */
export function dartCount(count: number): string {
  return count === 1
    ? $localize`:@@game.dartCountOne:1 Dart`
    : $localize`:@@game.dartCount:${count}:count: Darts`;
}
