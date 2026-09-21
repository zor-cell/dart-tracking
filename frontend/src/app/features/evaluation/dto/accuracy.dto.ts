import { GameMode } from '../../game/models/game-mode';

/** One band of the off-by distribution, e.g. `<= 5 mm`. */
export interface DistanceBandDto {
  readonly label: string;
  readonly darts: number;
}

export interface AccuracySummaryDto {
  readonly games: number;
  readonly visits: number;
  readonly cleanVisits: number;
  readonly dartsThrown: number;
  readonly dartsBooked: number;
  readonly correct: number;
  readonly wrong: number;
  readonly missed: number;
  readonly missedZeros: number;
  readonly phantom: number;
  readonly bands: readonly DistanceBandDto[];
  readonly meanOffBy: number | null;
  readonly medianOffBy: number | null;
  readonly worstOffBy: number | null;
}

export interface GameAccuracyDto {
  readonly gameId: string;
  readonly mode: GameMode;
  readonly createdAt: string;
  readonly evaluationEnabled: boolean;
  readonly summary: AccuracySummaryDto;
}

export interface AccuracyReportDto {
  readonly total: AccuracySummaryDto;
  readonly games: readonly GameAccuracyDto[];
}
