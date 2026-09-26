import { GameMode } from '../../game/models/game-mode';

/** One band of the off-by distribution, e.g. `<= 5 mm`. */
export interface DistanceBandDto {
  readonly label: string;
  readonly darts: number;
}

export type FieldKind = 'single' | 'double' | 'triple' | 'outside';

/** How the thrown darts that belonged in one kind of field were judged. */
export interface FieldErrorsDto {
  readonly kind: FieldKind;
  readonly thrown: number;
  readonly correct: number;
  readonly wrong: number;
  /** Booked in the right sector, but in another ring. */
  readonly wrongRing: number;
  readonly missed: number;
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
  readonly fields: readonly FieldErrorsDto[];
}

/** Viewing angles in degrees: horizontal < 0 is left of the board, vertical < 0 below the bull. */
export interface CameraAngleDto {
  readonly tilt: number;
  readonly horizontal: number;
  readonly vertical: number;
}

export interface GameAccuracyDto {
  readonly gameId: string;
  readonly mode: GameMode;
  readonly createdAt: string;
  readonly evaluationEnabled: boolean;
  readonly trackerVersion: number | null;
  readonly camera: CameraAngleDto | null;
  readonly summary: AccuracySummaryDto;
}

export interface AccuracyReportDto {
  readonly total: AccuracySummaryDto;
  readonly games: readonly GameAccuracyDto[];
}
