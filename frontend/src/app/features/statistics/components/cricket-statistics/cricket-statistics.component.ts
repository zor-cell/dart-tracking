import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DistanceScaleComponent } from '../../../game/components/distance-scale/distance-scale.component';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { CricketStatisticsDto } from '../../dto/cricket-statistics.dto';
import { HitPatternComponent } from '../hit-pattern/hit-pattern.component';
import { StatLinkComponent } from '../stat-link/stat-link.component';
import { StatSketchComponent } from '../stat-sketch/stat-sketch.component';

/** The visit bands by the fewest marks they take. */
const BANDS = [9, 7, 5, 3] as const;

/** Cricket: marks per round, how near the darts came to an open number, visits and where
 * the darts landed. */
@Component({
  selector: 'app-cricket-statistics',
  imports: [
    DecimalPipe,
    DistanceScaleComponent,
    HitPatternComponent,
    InfoHintComponent,
    StatLinkComponent,
    StatSketchComponent,
  ],
  templateUrl: './cricket-statistics.component.html',
  styleUrl: './cricket-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CricketStatisticsComponent {
  readonly statistics = input.required<CricketStatisticsDto>();

  protected readonly winRate = computed(() => {
    const { wins, gamesWithOpponent } = this.statistics();
    return share(wins, gamesWithOpponent);
  });
  protected readonly markedRate = computed(() => {
    const { empty, darts } = this.statistics();
    return share(darts - empty, darts);
  });

  /** Visits with at least each band's marks. */
  protected readonly bands = computed(() => {
    const visits = Object.entries(this.statistics().visits);
    return Object.fromEntries(
      BANDS.map((band) => [
        band,
        visits.reduce((sum, [marks, count]) => sum + (Number(marks) >= band ? count : 0), 0),
      ]),
    ) as Record<(typeof BANDS)[number], number>;
  });
}

/** `part` of `whole` in percent; null without a whole. */
function share(part: number, whole: number): number | null {
  return whole === 0 ? null : (100 * part) / whole;
}
