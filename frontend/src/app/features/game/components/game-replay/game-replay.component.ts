import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  effect,
  input,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { Select } from 'primeng/select';
import { SelectButton } from 'primeng/selectbutton';
import { Slider } from 'primeng/slider';
import { BoardHeatmapComponent } from '../../../statistics/components/board-heatmap/board-heatmap.component';
import { HeatmapPoint } from '../../../statistics/dto/player-statistics.dto';
import { HighlightedTip } from '../../../statistics/components/board-heatmap/board-heatmap.component';
import { PlayerDto } from '../../dto/player.dto';
import { DartDto } from '../../dto/dart.dto';
import { VisitDto } from '../../dto/visit.dto';
import { dartColor } from '../../models/dart-colors';
import { GameMode } from '../../models/game-mode';
import { GameVariant } from '../../models/game-variant';
import { ScoreboardEntry } from '../../models/scoreboard-entry';
import { labelPoints, ReplayPosition } from '../../models/visit';
import { ScoreDistributionComponent } from '../score-distribution/score-distribution.component';
import { FieldHeatmapComponent } from '../field-heatmap/field-heatmap.component';
import { ScoreRaceComponent } from '../score-race/score-race.component';
// import { ScoreboardComponent } from '../scoreboard/scoreboard.component';

/** Time per dart at normal speed, in milliseconds. */
const DART_INTERVAL_MS = 500;

/** Where the last chosen view is kept, so the next game opens on it. */
const VIEW_KEY = 'dart-tracking.gameView';

type ReplayView = 'heatmap' | 'race' | 'distribution';

type HeatmapLayer = 'fields' | 'tips';

const VIEWS: readonly { label: string; value: ReplayView }[] = [
  { label: 'Heatmap', value: 'heatmap' },
  { label: 'Verlauf', value: 'race' },
  { label: 'Visits', value: 'distribution' },
];

@Component({
  selector: 'app-game-replay',
  imports: [
    BoardHeatmapComponent,
    Button,
    FieldHeatmapComponent,
    FormsModule,
    ScoreDistributionComponent,
    ScoreRaceComponent,
    // ScoreboardComponent,
    Select,
    SelectButton,
    Slider,
  ],
  templateUrl: './game-replay.component.html',
  styleUrl: './game-replay.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
/** The game played back in one of three views, all driven by the same timeline. */
export class GameReplayComponent implements OnInit {
  readonly visits = input.required<readonly VisitDto[]>();
  readonly players = input.required<readonly PlayerDto[]>();
  readonly mode = input.required<GameMode>();
  readonly variant = input.required<GameVariant>();

  protected readonly viewOptions = [...VIEWS];
  protected readonly view = signal<ReplayView>(storedView());

  protected readonly speedOptions = [1, 2, 4].map((value) => ({ label: `${value}×`, value }));
  protected readonly playerOptions = computed(() => [
    { label: 'Alle Spieler', value: null },
    ...this.players().map((player) => ({ label: player.name, value: player.id })),
  ]);

  protected readonly layerOptions: { label: string; value: HeatmapLayer }[] = [
    { label: 'Felder', value: 'fields' },
    { label: 'Treffer', value: 'tips' },
  ];
  protected readonly layer = signal<HeatmapLayer>('fields');

  protected readonly speed = signal(1);
  protected readonly playerId = signal<number | null>(null);
  protected readonly playing = signal(false);
  /** How many darts of the replay are shown. */
  protected readonly cursor = signal(0);

  /** The replay's spot for the charts; before the first dart, no dart of visit 0. */
  protected readonly position = computed<ReplayPosition>(
    () => this.step() ?? { visit: 0, dart: -1 },
  );

  /** Visits whose last dart has been shown, counted in throwing order. */
  protected readonly shownVisits = computed(() => {
    const step = this.step();
    if (step === null) {
      return 0;
    }
    return this.visitComplete() ? step.visit + 1 : step.visit;
  });

  protected readonly steps = computed<ReplayPosition[]>(() => {
    const playerId = this.playerId();
    return this.visits().flatMap((visit, index) =>
      playerId !== null && visit.playerId !== playerId
        ? []
        : visit.darts.map((_, dart) => ({ visit: index, dart })),
    );
  });

  protected readonly step = computed(() => this.steps()[this.cursor() - 1] ?? null);

  protected readonly visit = computed(() => {
    const step = this.step();
    return step === null ? null : this.visits()[step.visit];
  });

  /** The darts of the visit on the board so far. */
  protected readonly boardDarts = computed(() => {
    const step = this.step();
    return step === null ? [] : this.visits()[step.visit].darts.slice(0, step.dart + 1);
  });

  /** Every dart up to the cursor, by field and, where located, by tip. */
  protected readonly trail = computed(() => {
    const visits = this.visits();
    const darts = this.steps()
      .slice(0, this.cursor())
      .map((step) => visits[step.visit].darts[step.dart]);
    return { labels: darts.map((dart) => dart.label), points: located(darts) };
  });

  /** The visit under way, the same two ways; tips keep their dart's colour. */
  protected readonly currentDarts = computed(() => ({
    labels: this.boardDarts().map((dart) => dart.label),
    tips: this.boardDarts().flatMap((dart, index): HighlightedTip[] =>
      dart.position === null
        ? []
        : [{ point: dart.position as HeatmapPoint, color: dartColor(index) }],
    ),
  }));

  protected readonly visitComplete = computed(() => {
    const step = this.step();
    return step !== null && step.dart === this.visits()[step.visit].darts.length - 1;
  });

  protected readonly totalRounds = computed(() =>
    Math.ceil(this.visits().length / this.players().length),
  );

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
    const standings = [...this.standings()];
    const elimination = this.variant() === 'elimination';
    // The thrower counts down dart by dart, as in the live game; a bust keeps the old score.
    const visit = this.visit();
    if (visit !== null && !this.visitComplete() && !visit.busted) {
      standings[visit.playerId] -= this.boardDarts().reduce(
        (sum, d) => sum + labelPoints(d.label),
        0,
      );
    }
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

  /** Opens on the finished game; playing starts over from the first dart. */
  ngOnInit(): void {
    this.cursor.set(this.steps().length);
  }

  protected selectView(view: ReplayView): void {
    this.view.set(view);
    try {
      localStorage.setItem(VIEW_KEY, view);
    } catch {
      // Storage can be unavailable (private mode); the choice then lasts this visit only.
    }
  }

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

  private roundOf(step: ReplayPosition): number {
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

function storedView(): ReplayView {
  try {
    const stored = localStorage.getItem(VIEW_KEY);
    return VIEWS.some((view) => view.value === stored) ? (stored as ReplayView) : 'heatmap';
  } catch {
    return 'heatmap';
  }
}

function located(darts: readonly DartDto[]): HeatmapPoint[] {
  return darts.flatMap((dart) => (dart.position === null ? [] : [dart.position as HeatmapPoint]));
}
