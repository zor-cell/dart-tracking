import { DecimalPipe, formatNumber } from '@angular/common';
import { ChangeDetectionStrategy, Component, LOCALE_ID, computed, inject, input } from '@angular/core';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { OverallStatisticsDto } from '../../dto/overall-statistics.dto';
import { duration } from '../../models/duration';
import { ActivityChartComponent } from '../activity-chart/activity-chart.component';
import { HitPatternComponent } from '../hit-pattern/hit-pattern.component';

/** One bar of a list: its name, its count and its length against the longest. */
interface BarRow {
  readonly key: string;
  readonly label: string;
  readonly count: number;
  readonly share: number;
  readonly figure: string;
}

/** The rings, the 25 counted as a single and the bull as a double. */
const RINGS: readonly { key: string; label: string }[] = [
  { key: 'single', label: 'Single' },
  { key: 'double', label: 'Double' },
  { key: 'triple', label: 'Triple' },
  { key: 'miss', label: $localize`:@@game.miss:Daneben` },
];

/** Every game of any kind: how much was played, where the darts went and when. */
@Component({
  selector: 'app-overall-statistics',
  imports: [ActivityChartComponent, DecimalPipe, HitPatternComponent, InfoHintComponent],
  templateUrl: './overall-statistics.component.html',
  styleUrl: './overall-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OverallStatisticsComponent {
  private readonly locale = inject(LOCALE_ID);

  readonly statistics = input.required<OverallStatisticsDto>();

  /** The time played, in hours from one hour up, else in minutes. */
  protected readonly playTime = computed(() => duration(this.statistics().seconds, this.locale));
  protected readonly timePerGame = computed(() => {
    const { seconds, games } = this.statistics();
    return games === 0 ? null : duration(seconds / games, this.locale);
  });

  protected readonly winRate = computed(() => {
    const { wins, gamesWithOpponent } = this.statistics();
    return gamesWithOpponent === 0 ? null : (100 * wins) / gamesWithOpponent;
  });

  protected readonly missRate = computed(() => share(this.statistics().misses, this.statistics().darts));
  protected readonly locatedRate = computed(() =>
    share(this.statistics().located, this.statistics().darts),
  );

  protected readonly rings = computed<BarRow[]>(() => {
    const { rings, darts } = this.statistics();
    const most = Math.max(1, ...Object.values(rings));
    return RINGS.map(({ key, label }) => {
      const count = rings[key] ?? 0;
      return {
        key,
        label,
        count,
        share: count / most,
        figure: `${formatNumber(share(count, darts) ?? 0, this.locale, '1.0-0')} %`,
      };
    });
  });
}

/** `part` of `whole` in percent; null without a whole. */
function share(part: number, whole: number): number | null {
  return whole === 0 ? null : (100 * part) / whole;
}
