/** A small figure beside the card's number: its value, the word under it, and what a screen reader says first. */
export interface ScoreboardFigure {
  readonly value: string;
  readonly label: string;
  readonly srLabel: string;
}

/** One Cricket target on a card: `marks` from 0 to 3, `dead` once everyone closed it. */
export interface CricketMark {
  readonly label: string;
  readonly marks: number;
  readonly dead: boolean;
}

/** One card of the scoreboard: the number is whatever the variant counts. */
export interface ScoreboardEntry {
  readonly id: number;
  readonly name: string;
  readonly score: string;
  readonly left: ScoreboardFigure;
  readonly right: ScoreboardFigure;
  /** Whether the player alone is closest to the win. */
  readonly leading: boolean;
  /** Whether the latest visit sent the player back to zero or knocked them out. */
  readonly reset: boolean;
  /** How often the player has sent another back to zero; null outside elimination. */
  readonly eliminations: number | null;
  /** Killer: whether the player may take lives. */
  readonly killer: boolean;
  /** Killer: whether the player has no lives left. */
  readonly out: boolean;
  /** A race: whether the player reached the goal; the last one left does not. */
  readonly finished: boolean;
  /** A race: whether the player sits out a tiebreak between those ahead. */
  readonly waiting: boolean;
  /** A race played for every place: the player's place once decided. */
  readonly place: number | null;
  /** Cricket: the marks per target; null in the other variants. */
  readonly marks: readonly CricketMark[] | null;
}
