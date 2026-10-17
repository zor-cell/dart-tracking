export interface LoginDto {
  /** Email or username. */
  readonly identifier: string;
  readonly password: string;
}
