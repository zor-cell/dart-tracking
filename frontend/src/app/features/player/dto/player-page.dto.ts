import { PlayerIdentityDto } from './player-identity.dto';

export interface PlayerPageDto {
  readonly items: readonly PlayerIdentityDto[];
  /** Entries across all pages. */
  readonly total: number;
}
