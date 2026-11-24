import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { ScoringStatisticsDto } from '../../dto/scoring-statistics.dto';
import { Comparison } from '../../models/comparison';
import { visitTotal } from '../../models/visit-scores';
import { ComparedValueComponent } from '../compared-value/compared-value.component';
import { DeltaMarkComponent } from '../delta-mark/delta-mark.component';
import { HitPatternComponent } from '../hit-pattern/hit-pattern.component';
import { StatLinkComponent } from '../stat-link/stat-link.component';

/** The visit bands; beside a compared player each as its share of the visits. */
const BANDS: readonly { label: string; count: (totals: ScoringStatisticsDto) => number }[] = [
  { label: '180', count: (totals) => totals.visits180 },
  { label: '140+', count: (totals) => totals.visits140Plus },
  { label: '100+', count: (totals) => totals.visits100Plus },
  { label: '60+', count: (totals) => totals.visits60Plus },
];

/** The points of the trainings without a target, as x01 counts them. */
@Component({
  selector: 'app-scoring-statistics',
  imports: [ComparedValueComponent, DecimalPipe, DeltaMarkComponent, HitPatternComponent, StatLinkComponent],
  templateUrl: './scoring-statistics.component.html',
  styleUrl: './scoring-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ScoringStatisticsComponent {
  readonly statistics = input.required<ScoringStatisticsDto>();
  readonly comparison = input<Comparison<ScoringStatisticsDto> | null>(null);

  protected readonly bands = computed(() => {
    const totals = this.statistics();
    const other = this.comparison()?.statistics ?? null;
    return BANDS.map(({ label, count }) => ({
      label,
      count: count(totals),
      share: share(totals, count(totals)),
      otherShare: other ? share(other, count(other)) : null,
    }));
  });
}

/** `count` visits in percent of all of them; null without a visit. */
function share(totals: ScoringStatisticsDto, count: number): number | null {
  const visits = visitTotal(totals.visitScores);
  return visits === 0 ? null : (100 * count) / visits;
}
