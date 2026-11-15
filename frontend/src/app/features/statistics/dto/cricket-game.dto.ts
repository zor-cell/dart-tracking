/** One Cricket game's figures. */
export interface CricketGameDto {
  readonly gameId: string;
  readonly playedAt: string;
  readonly won: boolean;
  readonly darts: number;
  readonly marks: number;
  /** Marks per three darts; null without a dart. */
  readonly mpr: number | null;
  /** Mean mm of the located darts from the nearest number still open; null without any. */
  readonly distance: number | null;
}
