import { GameSummaryDto } from './game-summary.dto';

export interface GamePageDto {
  readonly items: readonly GameSummaryDto[];
  /** Games matching the filter across all pages. */
  readonly total: number;
}
