import { GameVariant } from '../../game/models/game-variant';

/** What one bucket of the activity is cut into. */
export type ActivityUnit = 'day' | 'week' | 'month';

export interface ActivityTallyDto {
  readonly darts: number;
  readonly games: number;
  readonly seconds: number;
}

export interface ActivityBucketDto {
  /** The day, the Monday or the first of the month it starts on, as an ISO date. */
  readonly start: string;
  /** Only the variants played in it. */
  readonly variants: Partial<Readonly<Record<GameVariant, ActivityTallyDto>>>;
}

/** How much was played when, in buckets that fit the selected span. */
export interface ActivityDto {
  readonly unit: ActivityUnit;
  /** Oldest first, the empty ones included. */
  readonly buckets: readonly ActivityBucketDto[];
}
