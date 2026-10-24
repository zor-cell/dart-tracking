/** An active filter shown above a list; removing it clears the filter `key`. */
export interface FilterChip {
  readonly key: string;
  readonly label: string;
}
