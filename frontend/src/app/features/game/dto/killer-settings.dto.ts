import { KillerZone } from '../models/variant-options';

export interface KillerSettingsDto {
  readonly variant: 'killer';
  readonly lives: number;
  readonly zone: KillerZone;
}
