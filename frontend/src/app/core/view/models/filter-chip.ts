/** An active filter shown above a list; removing it clears the filter `key`. */
export interface FilterChip {
  readonly key: string;
  readonly label: string;
  /** False for a filter that is always set and only changes elsewhere. */
  readonly removable?: boolean;
  /** True when tapping the chip opens the page's own picker for this filter. */
  readonly opens?: boolean;
}

/** A chip that asked to open its picker, with the tap to anchor it to. */
export interface FilterChipOpen {
  readonly key: string;
  readonly event: Event;
}

/** A filter one tap away, offered beside the active ones; picking it sets `key` to `value`. */
export interface FilterSuggestion extends FilterChip {
  readonly value: unknown;
}

/** Picks of one filter as a chip reads them: "301", "301 oder 501", "301, 501 oder 701". */
export function orList(labels: readonly string[]): string {
  return labels.length < 2
    ? (labels[0] ?? '')
    : `${labels.slice(0, -1).join(', ')} oder ${labels.at(-1)}`;
}

/** Adds `value` to the picks of a list filter, once. */
export function withPick<T>(picks: readonly T[] | null | undefined, value: T): T[] {
  const current = picks ?? [];
  return current.includes(value) ? [...current] : [...current, value];
}
