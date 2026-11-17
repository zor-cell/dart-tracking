import { GameCommandDto } from './game-command.dto';

/** Client -> server: what a command changing a booked dart carries besides its own fields. */
export interface DartCorrectionDto extends GameCommandDto {
  /** The visit corrected, from 0; left out for the open one. */
  readonly turn?: number;
  /** Whether the consequence the server reported for this correction was accepted. */
  readonly confirmed?: boolean;
}
