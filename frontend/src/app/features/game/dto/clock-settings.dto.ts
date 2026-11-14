import { ClockZone } from '../models/variant-options';

export interface ClockSettingsDto {
  readonly variant: 'around_the_clock';
  readonly zone: ClockZone;
  /** Whether a double moves on two targets and a triple three. */
  readonly skip: boolean;
  readonly catchUp: boolean;
  readonly playOn: boolean;
}
