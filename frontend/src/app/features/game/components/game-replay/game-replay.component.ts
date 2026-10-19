import { ChangeDetectionStrategy, Component, computed, effect, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { Select } from 'primeng/select';
import { SelectButton } from 'primeng/selectbutton';
import { Slider } from 'primeng/slider';
import { BoardHeatmapComponent } from '../../../statistics/components/board-heatmap/board-heatmap.component';
import { HeatmapPoint } from '../../../statistics/dto/player-statistics.dto';
import { PlayerDto } from '../../dto/player.dto';
import { VisitDto } from '../../dto/visit.dto';
import { GameMode } from '../../models/game-mode';
import { GameVariant } from '../../models/game-variant';
import { ScoreboardEntry } from '../../models/scoreboard-entry';
import { ScoreboardComponent } from '../scoreboard/scoreboard.component';
import { VirtualBoardComponent } from '../virtual-board/virtual-board.component';

/** Time per dart at normal speed, in milliseconds. */
const DART_INTERVAL_MS = 500;

/** One dart of the replay: which visit, and which dart within it. */
interface ReplayStep {
  readonly visit: number;
  readonly dart: number;
}

@Component({
  selector: 'app-game-replay',
  imports: [
    BoardHeatmapComponent,
    Button,
    FormsModule,
    ScoreboardComponent,
    Select,
    SelectButton,
    Slider,
    VirtualBoardComponent,
  ],
  templateUrl: './game-replay.component.html',
  styleUrl: './game-replay.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameReplayComponent {
  readonly visits = input.required<readonly VisitDto[]>();
  readonly players = input.required<readonly PlayerDto[]>();
  readonly mode = input.required<GameMode>();
  readonly variant = input.required<GameVariant>();

  protected readonly speedOptions = [1, 2, 4].map((value) => ({ label: `${value}×`, value }));
  protected readonly playerOptions = computed(() => [
    { label: 'Alle Spieler', value: null },
    ...this.players().map((player) => ({ label: player.name, value: player.id })),
  ]);

  protected readonly speed = signal(1);
  protected readonly playerId = signal<number | null>(null);
  protected readonly playing = signal(false);
  /** Keep every dart so far on the board, as a heatmap, instead of only the visit's. */
  protected readonly keepDarts = signal(false);
  /** How many darts of the replay are shown. */
  protected readonly cursor = signal(0);

  protected readonly steps = computed<ReplayStep[]>(() => {
    const playerId = this.playerId();
    return this.visits().flatMap((visit, index) =>
      playerId !== null && visit.playerId !== playerId
        ? []
        : visit.darts.map((_, dart) => ({ visit: index, dart })),
    );
  });

  private readonly step = computed(() => this.steps()[this.cursor() - 1] ?? null);

  protected readonly visit = computed(() => {
    const step = this.step();
    return step === null ? null : this.visits()[step.visit];
  });

  /** The darts of the visit on the board so far. */
  protected readonly boardDarts = computed(() => {
    const step = this.step();
    return step === null ? [] : this.visits()[step.visit].darts.slice(0, step.dart + 1);
  });

  /** Every dart up to the cursor: located ones as points, entered ones by field. */
  protected readonly trail = computed(() => {
    const visits = this.visits();
    const darts = this.steps()
      .slice(0, this.cursor())
      .map((step) => visits[step.visit].darts[step.dart]);
    return {
      points: darts.flatMap((dart) => (dart.position === null ? [] : [dart.position as HeatmapPoint])),
      fields: darts.flatMap((dart) => (dart.position === null ? [dart.label] : [])),
    };
  });

  protected readonly visitComplete = computed(() => {
    const step = this.step();
    return step !== null && step.dart === this.visits()[step.visit].darts.length - 1;
  });

  /** Round of the visit on the board, counted over all players. */
  protected readonly round = computed(() => {
    const step = this.step();
    return step === null ? 0 : this.roundOf(step);
  });

  /** Points each player needed: after the visit once it is complete, before it until then. */
  protected readonly standings = computed(() => {
    const step = this.step();
    const players = this.players();
    if (step === null) {
      return players.map(() => this.mode());
    }
    const index = this.visitComplete() ? step.visit : step.visit - 1;
    return this.visits()[index]?.standings ?? players.map(() => this.mode());
  });

  /** Cards as in the live game: points still needed in x01, points gathered in elimination. */
  protected readonly scoreboardEntries = computed<ScoreboardEntry[]>(() => {
    const standings = this.standings();
    const elimination = this.variant() === 'elimination';
    return this.players().map((player) => ({
      id: player.id,
      name: player.name,
      score: elimination ? this.mode() - standings[player.id] : standings[player.id],
    }));
  });

  protected readonly activeIndex = computed(() => {
    const visit = this.visit();
    return visit === null ? null : this.players().findIndex((p) => p.id === visit.playerId);
  });

  /** The thrower once their visit finished the game. */
  protected readonly winnerId = computed(() => {
    const visit = this.visit();
    return visit !== null && this.visitComplete() && visit.standings[visit.playerId] === 0
      ? visit.playerId
      : null;
  });

  constructor() {
    effect((onCleanup) => {
      if (!this.playing()) {
        return;
      }
      const timer = setInterval(() => this.advance(), DART_INTERVAL_MS / this.speed());
      onCleanup(() => clearInterval(timer));
    });
  }

  protected togglePlay(): void {
    if (!this.playing() && this.cursor() >= this.steps().length) {
      this.cursor.set(0);
    }
    this.playing.update((playing) => !playing);
  }

  /** Turning the trail on while nothing is shown jumps to the end: the whole game at once. */
  protected setKeepDarts(keep: boolean): void {
    this.keepDarts.set(keep);
    if (keep && this.cursor() === 0 && !this.playing()) {
      this.cursor.set(this.steps().length);
    }
  }

  protected jumpTo(edge: 'start' | 'end'): void {
    this.playing.set(false);
    this.cursor.set(edge === 'start' ? 0 : this.steps().length);
  }

  protected stepBy(delta: -1 | 1): void {
    this.playing.set(false);
    this.seek(this.cursor() + delta);
  }

  protected seek(cursor: number): void {
    this.cursor.set(Math.min(Math.max(cursor, 0), this.steps().length));
  }

  /** Switch whose darts are replayed, staying at the same round and dart. */
  protected selectPlayer(playerId: number | null): void {
    const current = this.step();
    this.playerId.set(playerId);
    if (current === null) {
      return;
    }
    const steps = this.steps();
    const same = steps.findIndex((s) => s.visit === current.visit && s.dart === current.dart);
    if (same !== -1) {
      this.cursor.set(same + 1);
      return;
    }
    // A single player's steps run round by round, so the ones reached form a prefix.
    const round = this.roundOf(current);
    const reached = steps.filter(
      (s) => this.roundOf(s) < round || (this.roundOf(s) === round && s.dart <= current.dart),
    );
    this.cursor.set(reached.length);
  }

  private roundOf(step: ReplayStep): number {
    return Math.floor(step.visit / this.players().length) + 1;
  }

  private advance(): void {
    if (this.cursor() >= this.steps().length) {
      this.playing.set(false);
      return;
    }
    this.cursor.update((cursor) => cursor + 1);
  }
}
