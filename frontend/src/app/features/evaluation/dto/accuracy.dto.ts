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
  /** Missed darts the players booked as a zero. */
  readonly missedZeros: number;
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
  readonly trackerVersions: readonly number[];
  readonly camera: CameraAngleDto | null;
  readonly summary: AccuracySummaryDto;
}

export type GroupKind = 'version' | 'tilt' | 'fragments';

/** One group's darts and empty detections; `key` is a code such as `20-35` or `3+`. */
export interface GroupRowDto {
  readonly key: string;
  readonly summary: AccuracySummaryDto;
  readonly failures: readonly FailureCountDto[];
}

export interface GroupBreakdownDto {
  readonly kind: GroupKind;
  readonly rows: readonly GroupRowDto[];
}

/** Why detections came back empty, e.g. `no_change`. */
export interface FailureCountDto {
  readonly failure: string;
  readonly count: number;
}

export type DartOutcome = 'correct' | 'wrong' | 'missed' | 'phantom';

/** A dart the tracker got wrong; `offBy` in millimetres. */
export interface MismatchDto {
  readonly gameId: string;
  readonly turnIndex: number;
  readonly position: number;
  readonly outcome: DartOutcome;
  readonly tracked: string | null;
  readonly expected: string | null;
  readonly offBy: number | null;
  readonly fragments: number | null;
}

/** Where the camera located a booked dart, in board millimetres, the field it booked and how it was judged. */
export interface TipDto {
  readonly x: number;
  readonly y: number;
  readonly tracked: string;
  readonly outcome: DartOutcome;
}

export interface AccuracyReportDto {
  readonly total: AccuracySummaryDto;
  readonly games: readonly GameAccuracyDto[];
  readonly groups: readonly GroupBreakdownDto[];
  readonly failures: readonly FailureCountDto[];
  readonly mismatches: readonly MismatchDto[];
  readonly tips: readonly TipDto[];
}

/** One game on its own, with the darts the tracker got wrong in it. */
export interface GameReportDto {
  readonly game: GameAccuracyDto;
  readonly failures: readonly FailureCountDto[];
  readonly mismatches: readonly MismatchDto[];
  readonly tips: readonly TipDto[];
}
