/** An active filter shown above a list; removing it clears the filter `key`. */
export interface FilterChip {
  readonly key: string;
  readonly label: string;
  /** False for a filter that is always set and only changes elsewhere. */
  readonly removable?: boolean;
}

/** A filter one tap away, offered beside the active ones; picking it sets `key` to `value`. */
export interface FilterSuggestion extends FilterChip {
  readonly value: unknown;
}
