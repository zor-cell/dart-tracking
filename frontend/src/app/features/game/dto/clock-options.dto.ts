import { ClockZone } from '../models/variant-options';

export interface ClockOptionsDto {
  readonly zone: ClockZone;
  /** Whether a double moves on two targets and a triple three. */
  readonly skip: boolean;
}
