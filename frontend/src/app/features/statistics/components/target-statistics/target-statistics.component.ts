import { DecimalPipe, NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  input,
  signal,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SelectButton } from 'primeng/selectbutton';
import { DistanceScaleComponent } from '../../../game/components/distance-scale/distance-scale.component';
import {
  HEATMAP_LAYERS,
  HeatmapLayer,
  storeHeatmapLayer,
  storedHeatmapLayer,
} from '../../../game/models/heatmap-layer';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { TargetStatisticsDto } from '../../dto/target-statistics.dto';
import { COMPARE_COLOR, Comparison, OWN_COLOR } from '../../models/comparison';
import { StatisticsView, targetKey, targetLabel } from '../../models/statistics-game';
import { ComparedValueComponent } from '../compared-value/compared-value.component';
import { DeltaMarkComponent } from '../delta-mark/delta-mark.component';
import { StatSketchComponent } from '../stat-sketch/stat-sketch.component';
import { TargetBoardComponent } from '../target-board/target-board.component';
import { StatLinkComponent } from '../stat-link/stat-link.component';

/** Darts a target needs before it can be the strongest or weakest. */
const STRONGEST_MIN_DARTS = 5;

/** Games won out of those played, where the game has a winner to count (Killer). */
export interface TargetWins {
  readonly wins: number;
  readonly games: number;
}

/** The darts a player threw at named fields: key figures and where they landed. */
@Component({
  selector: 'app-target-statistics',
  imports: [
    ComparedValueComponent,
    DecimalPipe,
    DeltaMarkComponent,
    DistanceScaleComponent,
    FormsModule,
    InfoHintComponent,
    NgTemplateOutlet,
    SelectButton,
    StatLinkComponent,
    StatSketchComponent,
    TargetBoardComponent,
  ],
  templateUrl: './target-statistics.component.html',
  styleUrl: './target-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TargetStatisticsComponent {
  readonly statistics = input.required<TargetStatisticsDto>();
  readonly game = input.required<StatisticsView>();
  readonly wins = input<TargetWins | null>(null);
  readonly comparison = input<Comparison<TargetStatisticsDto> | null>(null);
  /** The compared player's wins, beside `wins`. */
  readonly otherWins = input<TargetWins | null>(null);

  protected readonly clock = computed(() => this.game() === 'around_the_clock');
  protected readonly pairColors = [OWN_COLOR, COMPARE_COLOR] as const;
  protected readonly layerOptions = [...HEATMAP_LAYERS];
  /** One layer for both boards of a comparison. */
  protected readonly layer = signal(storedHeatmapLayer());

  /** Key of the target picked on the board. */
  protected readonly selected = signal<string | null>(null);

  protected readonly rate = computed(() => hitRate(this.statistics()));
  protected readonly otherRate = computed(() => {
    const other = this.comparison()?.statistics;
    return other ? hitRate(other) : null;
  });
  protected readonly winRate = computed(() => winRate(this.wins()));
  protected readonly otherWinRate = computed(() => winRate(this.otherWins()));

  /** The ring most darts went at, which the distance is drawn beside. */
  protected readonly ring = computed(() => {
    const doubles = this.statistics()
      .fields.filter((field) => field.multiplier === 2)
      .reduce((sum, field) => sum + field.darts, 0);
    return doubles * 2 > this.statistics().darts ? 'double' : 'other';
  });

  private readonly ranked = computed(() => ranked(this.statistics()));
  private readonly otherRanked = computed(() => {
    const other = this.comparison()?.statistics;
    return other ? ranked(other) : [];
  });
  protected readonly strongest = computed(() => this.ranked().at(0) ?? null);
  protected readonly weakest = computed(() => weakest(this.ranked()));
  protected readonly otherStrongest = computed(() => this.otherRanked().at(0)?.label ?? null);
  protected readonly otherWeakest = computed(() => weakest(this.otherRanked())?.label ?? null);

  constructor() {
    // New figures drop a pick that is no longer among their targets.
    effect(() => {
      const keys = [
        ...this.statistics().fields,
        ...(this.comparison()?.statistics.fields ?? []),
      ].map(targetKey);
      untracked(() => {
        if (!keys.includes(this.selected() ?? '')) {
          this.selected.set(null);
        }
      });
    });
  }

  protected selectLayer(layer: HeatmapLayer): void {
    this.layer.set(layer);
    storeHeatmapLayer(layer);
  }
}

function hitRate({ darts, hits }: TargetStatisticsDto): number | null {
  return darts === 0 ? null : (100 * hits) / darts;
}

function winRate(wins: TargetWins | null): number | null {
  return wins && wins.games > 0 ? (100 * wins.wins) / wins.games : null;
}

/** Targets with enough darts to count, best hit rate first. */
function ranked(statistics: TargetStatisticsDto): { label: string; rate: number }[] {
  return statistics.fields
    .filter((field) => field.darts >= STRONGEST_MIN_DARTS)
    .map((field) => ({ label: targetLabel(field), rate: (100 * field.hits) / field.darts }))
    .sort((a, b) => b.rate - a.rate);
}

function weakest<T>(ranked: readonly T[]): T | null {
  return ranked.length > 1 ? ranked[ranked.length - 1] : null;
}
