import {GameMode} from "../models/game-mode";

export interface GameConfigDto {
  readonly playerNames: readonly string[];
  readonly mode: GameMode;
}