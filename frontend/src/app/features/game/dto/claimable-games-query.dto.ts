import { GameClaimTokenDto } from './game-claim-token.dto';

export interface ClaimableGamesQueryDto {
  readonly claims: readonly GameClaimTokenDto[];
}
