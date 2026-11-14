import { GameSettingsDto } from './game-settings.dto';

export interface QuickStartSeatDto {
  /** The identity to seat, or null to seat a guest by `name`. */
  readonly playerId: string | null;
  readonly name: string;
}

/** The setup the account plays most, with the players of its latest game. */
export interface QuickStartDto {
  readonly settings: GameSettingsDto;
  readonly players: readonly QuickStartSeatDto[];
}
