import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { ScoringStatisticsDto } from '../../dto/scoring-statistics.dto';
import { HitPatternComponent } from '../hit-pattern/hit-pattern.component';
import { StatLinkComponent } from '../stat-link/stat-link.component';

/** The points of the trainings without a target, as x01 counts them. */
@Component({
  selector: 'app-scoring-statistics',
  imports: [DecimalPipe, HitPatternComponent, StatLinkComponent],
  templateUrl: './scoring-statistics.component.html',
  styleUrl: './scoring-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ScoringStatisticsComponent {
  readonly statistics = input.required<ScoringStatisticsDto>();

  protected readonly bands = computed(() => {
    const totals = this.statistics();
    return [
      { label: '180', count: totals.visits180 },
      { label: '140+', count: totals.visits140Plus },
      { label: '100+', count: totals.visits100Plus },
      { label: '60+', count: totals.visits60Plus },
    ];
  });
}
