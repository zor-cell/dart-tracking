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
import { DistanceScaleComponent } from '../../../game/components/distance-scale/distance-scale.component';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { TargetStatisticsDto } from '../../dto/target-statistics.dto';
import { StatisticsView, targetKey, targetLabel } from '../../models/statistics-game';
import { StatSketchComponent } from '../stat-sketch/stat-sketch.component';
import { TargetBoardComponent } from '../target-board/target-board.component';
import { StatLinkComponent } from '../stat-link/stat-link.component';

/** Darts a target needs before it can be the strongest or weakest. */
const STRONGEST_MIN_DARTS = 5;

/** The darts a player threw at named fields: key figures and where they landed. */
@Component({
  selector: 'app-target-statistics',
  imports: [
    DecimalPipe,
    DistanceScaleComponent,
    InfoHintComponent,
    NgTemplateOutlet,
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
  /** Games won out of those played, where the game has a winner to count (Killer). */
  readonly wins = input<{ readonly wins: number; readonly games: number } | null>(null);
  /** Heading of the key figures in place of "Allgemein", and a line of what they count. */
  readonly title = input<string | null>(null);
  readonly hint = input<string | null>(null);

  protected readonly clock = computed(() => this.game() === 'around_the_clock');


  /** Key of the target picked on the board. */
  protected readonly selected = signal<string | null>(null);

  protected readonly rate = computed(() => {
    const { darts, hits } = this.statistics();
    return darts === 0 ? null : (100 * hits) / darts;
  });

  /** The ring most darts went at, which the distance is drawn beside. */
  protected readonly ring = computed(() => {
    const doubles = this.statistics()
      .fields.filter((field) => field.multiplier === 2)
      .reduce((sum, field) => sum + field.darts, 0);
    return doubles * 2 > this.statistics().darts ? 'double' : 'other';
  });

  /** Targets with enough darts to count, best hit rate first. */
  private readonly ranked = computed(() =>
    this.statistics()
      .fields.filter((field) => field.darts >= STRONGEST_MIN_DARTS)
      .map((field) => ({ label: targetLabel(field), rate: (100 * field.hits) / field.darts }))
      .sort((a, b) => b.rate - a.rate),
  );
  protected readonly strongest = computed(() => this.ranked().at(0) ?? null);
  protected readonly weakest = computed(() => {
    const ranked = this.ranked();
    return ranked.length > 1 ? ranked[ranked.length - 1] : null;
  });

  constructor() {
    // New figures drop a pick that is no longer among their targets.
    effect(() => {
      const keys = this.statistics().fields.map(targetKey);
      untracked(() => {
        if (!keys.includes(this.selected() ?? '')) {
          this.selected.set(null);
        }
      });
    });
  }
}
