/** A box of grid cells, as the trigger's counts and spans use them. */
export interface TriggerChangeDto {
  readonly col: number;
  readonly row: number;
  readonly cols: number;
  readonly rows: number;
}
