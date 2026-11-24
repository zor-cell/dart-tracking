import { DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DistanceScaleComponent } from '../../../game/components/distance-scale/distance-scale.component';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { CricketStatisticsDto } from '../../dto/cricket-statistics.dto';
import { COMPARE_COLOR, Comparison, OWN_COLOR } from '../../models/comparison';
import { ComparedValueComponent } from '../compared-value/compared-value.component';
import { DeltaMarkComponent } from '../delta-mark/delta-mark.component';
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
    ComparedValueComponent,
    DecimalPipe,
    DeltaMarkComponent,
    DistanceScaleComponent,
    HitPatternComponent,
    InfoHintComponent,
    NgTemplateOutlet,
    StatLinkComponent,
    StatSketchComponent,
  ],
  templateUrl: './cricket-statistics.component.html',
  styleUrl: './cricket-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CricketStatisticsComponent {
  readonly statistics = input.required<CricketStatisticsDto>();
  readonly comparison = input<Comparison<CricketStatisticsDto> | null>(null);

  protected readonly pairColors = [OWN_COLOR, COMPARE_COLOR] as const;

  protected readonly winRate = computed(() => winRate(this.statistics()));
  protected readonly otherWinRate = computed(() => {
    const other = this.comparison()?.statistics;
    return other ? winRate(other) : null;
  });
  protected readonly markedRate = computed(() => markedRate(this.statistics()));
  protected readonly otherMarkedRate = computed(() => {
    const other = this.comparison()?.statistics;
    return other ? markedRate(other) : null;
  });

  /** Visits with at least each band's marks; beside a compared player as shares of the visits. */
  protected readonly bands = computed(() => {
    const own = this.statistics();
    const other = this.comparison()?.statistics ?? null;
    return BANDS.map((band) => ({
      label: band === 9 ? '9 Marks' : `${band}+`,
      count: atLeast(own, band),
      share: share(atLeast(own, band), visits(own)),
      otherShare: other ? share(atLeast(other, band), visits(other)) : null,
    }));
  });
}

function winRate({ wins, gamesWithOpponent }: CricketStatisticsDto): number | null {
  return share(wins, gamesWithOpponent);
}

function markedRate({ empty, darts }: CricketStatisticsDto): number | null {
  return share(darts - empty, darts);
}

function atLeast(totals: CricketStatisticsDto, band: number): number {
  return Object.entries(totals.visits).reduce(
    (sum, [marks, count]) => sum + (Number(marks) >= band ? count : 0),
    0,
  );
}

function visits(totals: CricketStatisticsDto): number {
  return Object.values(totals.visits).reduce((sum, count) => sum + count, 0);
}

/** `part` of `whole` in percent; null without a whole. */
function share(part: number, whole: number): number | null {
  return whole === 0 ? null : (100 * part) / whole;
}
