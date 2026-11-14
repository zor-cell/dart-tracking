import { GameSettingsDto } from './game-settings.dto';
import { PlayerSlotDto } from './player-slot.dto';

export interface GameConfigDto {
  readonly players: readonly PlayerSlotDto[];
  readonly settings: GameSettingsDto;
  readonly evaluationEnabled: boolean;
  readonly rematchOf?: string;
}
