import { CricketScoring } from '../models/variant-options';

export interface CricketSettingsDto {
  readonly variant: 'cricket';
  readonly scoring: CricketScoring;
}
