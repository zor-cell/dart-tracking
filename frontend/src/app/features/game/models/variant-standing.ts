import { GameStateDto } from '../dto/game-state.dto';
import { playOf } from './game-settings';
import { CricketMark, ScoreboardFigure } from './scoreboard-entry';
import { fieldLabel, zoneLabel } from './variant-options';

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
  /** How far through a race with a fixed course, in percent; null without one. */
  readonly progress: number | null;
}

/** Formats a number the way the view's locale writes it, e.g. `1.1-1` digits. */
export type NumberFormat = (value: number, digits: string) => string;

const NONE = '–';
const DONE = '✓';
const MARKS_TO_CLOSE = 3;
// Around the clock: 1 to 20, then the bull.
const CLOCK_TARGETS = 21;

/** Every player's standing, in seat order. */
export function standings(state: GameStateDto, format: NumberFormat): Standing[] {
  return state.players.map((player, seat) => {
    const read = standingOf(state, seat, format);
    const done = player.id === state.winnerId || state.finisherIds.includes(player.id);
    const standing = done ? { ...read, score: DONE } : read;
    if (player.id === state.winnerId) {
      return { ...standing, rank: Number.POSITIVE_INFINITY };
    }
    const place = state.places.indexOf(player.id);
    return place < 0 ? standing : { ...standing, rank: Number.MAX_SAFE_INTEGER - place };
  });
}

function standingOf(state: GameStateDto, seat: number, format: NumberFormat): Standing {
  const plain = { killer: false, out: false, marks: null, progress: null };
  const last = $localize`:@@game.scoreboard.last:letzte`;

  const play = playOf(state);

  if (play.variant === 'cricket') {
    const cricket = play.standing;
    const scoring = play.settings.scoring;
    const player = cricket.players[seat];
    const closed = player.marks.filter((marks) => marks >= MARKS_TO_CLOSE).length;
    const total = player.marks.reduce((sum, marks) => sum + marks, 0);
    const points = { standard: player.points, cut_throat: -player.points, no_score: 0 }[scoring];
    return {
      ...plain,
      score: scoring === 'no_score' ? `${closed}/${cricket.targets.length}` : `${player.points}`,
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
        label: `${target}`,
        marks: player.marks[index],
        dead: cricket.players.every((other) => other.marks[index] >= MARKS_TO_CLOSE),
      })),
    };
  }

  if (play.variant === 'killer') {
    const player = play.standing.players[seat];
    return {
      ...plain,
      score: zoneLabel(player.number, play.settings.zone),
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

  if (play.variant === 'training') {
    const own = play.standing.players[seat];
    const player = state.players[seat];
    const free = own.target === null;
    const rate = own.darts === 0 ? NONE : `${format((100 * own.hits) / own.darts, '1.0-0')} %`;
    const visit = free ? player.lastVisit : own.lastVisit;
    return {
      ...plain,
      // A free training keeps its average as the result; a training at targets is done.
      score: free
        ? player.average === null
          ? NONE
          : format(player.average, '1.1-1')
        : state.ended
          ? DONE
          : fieldLabel(own.target),
      left: free
        ? { value: `${own.darts}`, label: 'Darts', srLabel: 'Darts' }
        : {
            value: rate,
            label: $localize`:@@game.scoreboard.hitRate:Quote`,
            srLabel: $localize`:@@game.scoreboard.hitRateLong:Trefferquote`,
          },
      right: {
        value: visit === null ? NONE : `${visit}`,
        label: last,
        srLabel: free
          ? $localize`:@@game.scoreboard.lastVisit:Letzter Visit`
          : $localize`:@@game.scoreboard.lastHits:Treffer im letzten Visit`,
      },
      rank: free ? (player.average ?? 0) : own.hits,
    };
  }

  if (play.variant === 'personal') {
    const own = play.standing.players[seat];
    const blocks = play.standing.blocks;
    const tally = own.blocks[Math.min(own.block, blocks.length - 1)];
    const rate = tally === undefined || tally.darts === 0 ? NONE : `${format((100 * tally.hits) / tally.darts, '1.0-0')} %`;
    return {
      ...plain,
      score: own.target === null || state.ended ? DONE : fieldLabel(own.target),
      left: {
        value: rate,
        label: $localize`:@@game.scoreboard.hitRate:Quote`,
        srLabel: $localize`:@@game.scoreboard.blockHitRate:Trefferquote im Block`,
      },
      right: {
        value: `${Math.min(own.block + 1, blocks.length)}/${blocks.length}`,
        label: 'Block',
        srLabel: 'Block',
      },
      rank: own.darts,
    };
  }

  if (play.variant === 'around_the_clock') {
    const player = play.standing.players[seat];
    return {
      ...plain,
      score: player.target === null ? DONE : zoneLabel(player.target, play.settings.zone),
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
      progress: (100 * player.done) / CLOCK_TARGETS,
    };
  }

  const player = state.players[seat];
  const remaining = player.remaining ?? 0;
  return {
    ...plain,
    // Points still needed in x01, points gathered in elimination: one value from opposite ends.
    score: `${play.variant === 'elimination' ? play.settings.mode - remaining : remaining}`,
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
