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
import { countFields } from '../../models/field-label';
import {
  HEATMAP_LAYERS,
  HeatmapLayer,
  storeHeatmapLayer,
  storedHeatmapLayer,
} from '../../models/heatmap-layer';
import { TipPoint } from '../../models/tip-density';
import { PlayerDto } from '../../dto/player.dto';
import { VisitDto } from '../../dto/visit.dto';
import { GameMode } from '../../models/game-mode';
import { GameVariant } from '../../models/game-variant';
import { ReplayPosition } from '../../models/visit';
import { ScoreDistributionComponent } from '../score-distribution/score-distribution.component';
import { FieldHeatmapComponent } from '../field-heatmap/field-heatmap.component';
import { ScoreRaceComponent } from '../score-race/score-race.component';
import { TipHeatmapComponent } from '../tip-heatmap/tip-heatmap.component';
import { readStored, writeStored } from '../../../../core/storage/models/browser-storage';

/** Time per dart at normal speed, in milliseconds. */
const DART_INTERVAL_MS = 500;

/** Where the last chosen view is kept, so the next game opens on it. */
const VIEW_KEY = 'dart-tracking.gameView';

type ReplayView = 'heatmap' | 'race' | 'distribution';

const VIEWS: readonly { label: string; value: ReplayView }[] = [
  { label: 'Heatmap', value: 'heatmap' },
  { label: 'Verlauf', value: 'race' },
  { label: 'Streuung', value: 'distribution' },
];

@Component({
  selector: 'app-game-replay',
  imports: [
    Button,
    FieldHeatmapComponent,
    FormsModule,
    ScoreDistributionComponent,
    ScoreRaceComponent,
    Select,
    SelectButton,
    Slider,
    TipHeatmapComponent,
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
  protected readonly view = signal<ReplayView>(
    stored(
      VIEW_KEY,
      VIEWS.map((view) => view.value),
      'heatmap',
    ),
  );

  protected readonly speedOptions = [1, 2, 4].map((value) => ({ label: `${value}×`, value }));
  protected readonly playerOptions = computed(() => [
    { label: 'Alle Spieler', value: null },
    ...this.players().map((player) => ({ label: player.name, value: player.id })),
  ]);

  protected readonly layerOptions = [...HEATMAP_LAYERS];
  protected readonly layer = signal(storedHeatmapLayer());
  /** The field picked on the heatmap, kept when the layer changes. */
  protected readonly pinnedField = signal<string | null>(null);

  protected readonly speed = signal(1);
  protected readonly playerId = signal<number | null>(null);
  protected readonly playing = signal(false);
  /** How many darts of the replay are shown; one past the last dart is the end state. */
  protected readonly cursor = signal(0);

  /** The cursor of the end state: the whole game, with no visit highlighted. */
  protected readonly end = computed(() =>
    this.steps().length === 0 ? 0 : this.steps().length + 1,
  );
  protected readonly atEnd = computed(() => this.end() > 0 && this.cursor() === this.end());

  /** The replay's spot for the charts; before the first dart, no dart of visit 0; at the end, none. */
  protected readonly position = computed<ReplayPosition | null>(() =>
    this.atEnd() ? null : (this.step() ?? { visit: 0, dart: -1 }),
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

  protected readonly step = computed(
    () => this.steps()[Math.min(this.cursor(), this.steps().length) - 1] ?? null,
  );

  /** The darts of the visit on the board so far; none at the end state. */
  protected readonly boardDarts = computed(() => {
    const step = this.step();
    return step === null || this.atEnd()
      ? []
      : this.visits()[step.visit].darts.slice(0, step.dart + 1);
  });

  /** Every dart up to the cursor, by field and, where located, by tip. */
  protected readonly trail = computed(() => {
    const visits = this.visits();
    const darts = this.steps()
      .slice(0, this.cursor())
      .map((step) => visits[step.visit].darts[step.dart]);
    const located = darts.filter((dart) => dart.position !== null);
    return {
      labels: darts.map((dart) => dart.label),
      located: located.map((dart) => dart.label),
      points: located.map((dart) => dart.position as TipPoint),
    };
  });

  protected readonly fieldCounts = computed(() => countFields(this.trail().labels));
  protected readonly tipCounts = computed(() => countFields(this.trail().located));

  protected readonly visitComplete = computed(() => {
    const step = this.step();
    return step !== null && step.dart === this.visits()[step.visit].darts.length - 1;
  });

  protected readonly totalRounds = computed(() =>
    Math.ceil(this.visits().length / this.players().length),
  );

  /** Visits in the replay in throwing order, only the chosen player's when one is picked. */
  private readonly replayedVisits = computed(() => [
    ...new Set(this.steps().map((step) => step.visit)),
  ]);

  protected readonly visitCount = computed(() => this.replayedVisits().length);
  protected readonly dartCount = computed(() => this.steps().length);

  /** Number of the visit on the board among the replayed ones, so it ends at `visitCount`. */
  protected readonly visitNumber = computed(() => {
    const step = this.step();
    return step === null ? 0 : this.replayedVisits().indexOf(step.visit) + 1;
  });

  /** Round of the visit on the board, counted over all players. */
  protected readonly round = computed(() => {
    const step = this.step();
    return step === null ? 0 : this.roundOf(step);
  });

  /** Opens on the end state; playing starts over from the first dart. */
  ngOnInit(): void {
    this.cursor.set(this.end());
  }

  protected selectView(view: ReplayView): void {
    this.view.set(view);
    writeStored(VIEW_KEY, view);
  }

  protected selectLayer(layer: HeatmapLayer): void {
    this.layer.set(layer);
    storeHeatmapLayer(layer);
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
    if (!this.playing() && this.cursor() >= this.end()) {
      this.cursor.set(0);
    }
    this.playing.update((playing) => !playing);
  }

  protected jumpTo(edge: 'start' | 'end'): void {
    this.playing.set(false);
    this.cursor.set(edge === 'start' ? 0 : this.end());
  }

  protected stepBy(delta: -1 | 1): void {
    this.playing.set(false);
    this.seek(this.cursor() + delta);
  }

  protected seek(cursor: number): void {
    this.cursor.set(Math.min(Math.max(cursor, 0), this.end()));
  }

  /** Switch whose darts are replayed, staying at the same round and dart. */
  protected selectPlayer(playerId: number | null): void {
    const current = this.step();
    const atEnd = this.atEnd();
    this.playerId.set(playerId);
    if (atEnd) {
      this.cursor.set(this.end());
      return;
    }
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
    if (this.cursor() >= this.end()) {
      this.playing.set(false);
      return;
    }
    this.cursor.update((cursor) => cursor + 1);
  }
}

/** The value kept under `key`, if it is still one of `allowed`. */
function stored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  const value = readStored(key);
  return allowed.find((option) => option === value) ?? fallback;
}
