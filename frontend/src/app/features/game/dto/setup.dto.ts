/** Darts to throw when the visit cannot finish, and the points they leave. */
export interface SetupDto {
  readonly darts: readonly string[];
  readonly leave: number;
}
