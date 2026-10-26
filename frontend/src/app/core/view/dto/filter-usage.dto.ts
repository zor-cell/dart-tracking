/** A filter the account picked in one of its lists; `value` is JSON, so numbers stay numbers. */
export interface FilterUseDto {
  readonly view: string;
  readonly key: string;
  readonly value: string;
  /** Weight that fades with the time since `lastUsedAt`. */
  readonly score: number;
  readonly lastUsedAt: string;
}

/** All of the account's picks, as the server stores them without reading them. */
export interface FilterUsageDto {
  readonly uses: readonly FilterUseDto[];
}
