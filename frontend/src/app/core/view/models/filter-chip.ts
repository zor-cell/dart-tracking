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

/** Picks a chip names before it counts the rest. */
const NAMED_PICKS = 2;

/** Picks of one filter as a chip reads them: "301", "301 oder 501", "Anna, Ben +3". */
export function orList(labels: readonly string[]): string {
  if (labels.length > NAMED_PICKS) {
    return `${labels.slice(0, NAMED_PICKS).join(', ')} +${labels.length - NAMED_PICKS}`;
  }
  return labels.join(' oder ');
}

/** Adds `value` to the picks of a list filter, once. */
export function withPick<T>(picks: readonly T[] | null | undefined, value: T): T[] {
  const current = picks ?? [];
  return current.includes(value) ? [...current] : [...current, value];
}
