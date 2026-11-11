import { KillerZone } from '../models/variant-options';

export interface KillerOptionsDto {
  readonly lives: number;
  readonly zone: KillerZone;
}
