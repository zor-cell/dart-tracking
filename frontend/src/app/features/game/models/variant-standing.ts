import { GameStateDto } from '../dto/game-state.dto';
import { CricketMark, ScoreboardFigure } from './scoreboard-entry';
import { zoneLabel } from './variant-options';

/** How one player stands, read off the variant that is played. */
export interface Standing {
  readonly score: string;
  readonly left: ScoreboardFigure;
  readonly right: ScoreboardFigure;
  /** Higher is closer to the win; the winner ranks highest. */
  readonly rank: number;
  readonly killer: boolean;
  readonly out: boolean;
  readonly marks: readonly CricketMark[] | null;
}

/** Formats a number the way the view's locale writes it, e.g. `1.1-1` digits. */
export type NumberFormat = (value: number, digits: string) => string;

const NONE = '–';
const MARKS_TO_CLOSE = 3;

/** Every player's standing, in seat order. */
export function standings(state: GameStateDto, format: NumberFormat): Standing[] {
  return state.players.map((player, seat) => {
    const standing = standingOf(state, seat, format);
    if (player.id === state.winnerId) {
      return { ...standing, rank: Number.POSITIVE_INFINITY };
    }
    const place = state.places.indexOf(player.id);
    return place < 0 ? standing : { ...standing, rank: Number.MAX_SAFE_INTEGER - place };
  });
}

function standingOf(state: GameStateDto, seat: number, format: NumberFormat): Standing {
  const plain = { killer: false, out: false, marks: null };
  const last = $localize`:@@game.scoreboard.last:letzte`;

  if (state.cricket !== null) {
    const cricket = state.cricket;
    const player = cricket.players[seat];
    const closed = player.marks.filter((marks) => marks >= MARKS_TO_CLOSE).length;
    const total = player.marks.reduce((sum, marks) => sum + marks, 0);
    const points = { standard: player.points, cut_throat: -player.points, no_score: 0 }[cricket.scoring];
    return {
      ...plain,
      score: cricket.scoring === 'no_score' ? `${closed}/${cricket.targets.length}` : `${player.points}`,
      left: {
        value: player.marksPerRound === null ? NONE : format(player.marksPerRound, '1.1-1'),
        label: 'MPR',
        srLabel: $localize`:@@game.scoreboard.marksPerRound:Marks pro Runde`,
      },
      right: {
        value: player.lastVisit === null ? NONE : `${player.lastVisit}`,
        label: last,
        srLabel: $localize`:@@game.scoreboard.lastMarks:Marks im letzten Visit`,
      },
      rank: total * 10_000 + points,
      marks: cricket.targets.map((target, index) => ({
        label: target === 25 ? 'B' : `${target}`,
        marks: player.marks[index],
        dead: cricket.players.every((other) => other.marks[index] >= MARKS_TO_CLOSE),
      })),
    };
  }

  if (state.killer !== null) {
    const killer = state.killer;
    const player = killer.players[seat];
    return {
      ...plain,
      score: zoneLabel(player.number, killer.zone),
      left: {
        value: `${player.lives}`,
        label: $localize`:@@game.scoreboard.lives:Leben`,
        srLabel: $localize`:@@game.scoreboard.lives:Leben`,
      },
      right: {
        value: `${player.kills}`,
        label: $localize`:@@game.scoreboard.kills:Abschüsse`,
        srLabel: $localize`:@@game.scoreboard.kills:Abschüsse`,
      },
      rank: player.lives,
      killer: player.killer,
      out: player.lives === 0,
    };
  }

  if (state.aroundTheClock !== null) {
    const clock = state.aroundTheClock;
    const player = clock.players[seat];
    return {
      ...plain,
      score: player.target === null ? '✓' : player.target === 25 ? 'Bull' : `${player.target}`,
      left: {
        value: player.darts === 0 ? NONE : `${format((100 * player.hits) / player.darts, '1.0-0')} %`,
        label: $localize`:@@game.scoreboard.hitRate:Quote`,
        srLabel: $localize`:@@game.scoreboard.hitRateLong:Trefferquote`,
      },
      right: {
        value: player.lastVisit === null ? NONE : `+${player.lastVisit}`,
        label: last,
        srLabel: $localize`:@@game.scoreboard.lastSteps:Felder im letzten Visit`,
      },
      rank: player.done,
    };
  }

  const player = state.players[seat];
  const remaining = player.remaining ?? 0;
  const mode = state.mode ?? 0;
  return {
    ...plain,
    // Points still needed in x01, points gathered in elimination: one value from opposite ends.
    score: `${state.variant === 'elimination' ? mode - remaining : remaining}`,
    left: {
      value: player.average === null ? NONE : format(player.average, '1.1-1'),
      label: 'Ø',
      srLabel: 'Average',
    },
    right: {
      value: player.lastVisit === null ? NONE : `${player.lastVisit}`,
      label: last,
      srLabel: $localize`:@@game.scoreboard.lastVisit:Letzter Visit`,
    },
    rank: -remaining,
  };
}
