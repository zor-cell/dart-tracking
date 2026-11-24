import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, LOCALE_ID, computed, inject, input } from '@angular/core';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { ActivityDto } from '../../dto/activity.dto';
import { OverallStatisticsDto } from '../../dto/overall-statistics.dto';
import { COMPARE_COLOR, Comparison, OWN_COLOR } from '../../models/comparison';
import { duration } from '../../models/duration';
import { ActivityChartComponent } from '../activity-chart/activity-chart.component';
import { ComparedValueComponent } from '../compared-value/compared-value.component';
import { DeltaMarkComponent } from '../delta-mark/delta-mark.component';
import { HitPatternComponent } from '../hit-pattern/hit-pattern.component';

/** One ring: its share of the darts and its bar's length against the longest, both players'. */
interface RingRow {
  readonly key: string;
  readonly label: string;
  readonly percent: number | null;
  readonly width: number;
  readonly otherPercent: number | null;
  readonly otherWidth: number;
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
  imports: [
    ActivityChartComponent,
    ComparedValueComponent,
    DecimalPipe,
    DeltaMarkComponent,
    HitPatternComponent,
    InfoHintComponent,
  ],
  templateUrl: './overall-statistics.component.html',
  styleUrl: './overall-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OverallStatisticsComponent {
  private readonly locale = inject(LOCALE_ID);

  readonly statistics = input.required<OverallStatisticsDto>();
  readonly comparison = input<Comparison<OverallStatisticsDto> | null>(null);

  protected readonly ownColor = OWN_COLOR;
  protected readonly compareColor = COMPARE_COLOR;

  /** The time played, in hours from one hour up, else in minutes. */
  protected readonly playTime = computed(() => duration(this.statistics().seconds, this.locale));
  protected readonly otherPlayTime = computed(() => {
    const other = this.comparison()?.statistics;
    return other ? duration(other.seconds, this.locale) : null;
  });
  protected readonly timePerGame = computed(() => {
    const { seconds, games } = this.statistics();
    return games === 0 ? null : duration(seconds / games, this.locale);
  });

  protected readonly winRate = computed(() => winRate(this.statistics()));
  protected readonly missRate = computed(() => missRate(this.statistics()));
  protected readonly locatedRate = computed(() => locatedRate(this.statistics()));
  protected readonly otherWinRate = computed(() => this.other(winRate));
  protected readonly otherMissRate = computed(() => this.other(missRate));
  protected readonly otherLocatedRate = computed(() => this.other(locatedRate));

  protected readonly otherActivity = computed<Comparison<ActivityDto> | null>(() => {
    const other = this.comparison();
    return other?.statistics.activity ? { name: other.name, statistics: other.statistics.activity } : null;
  });

  /** Without a comparison a bar's length is its count against the most; beside another
   * player it is its share of the darts, both on one scale. */
  protected readonly rings = computed<RingRow[]>(() => {
    const own = this.statistics();
    const other = this.comparison()?.statistics ?? null;
    const percents = RINGS.map(({ key }) => ({
      own: share(own.rings[key] ?? 0, own.darts),
      other: other ? share(other.rings[key] ?? 0, other.darts) : null,
    }));
    const most = Math.max(1, ...percents.flatMap(({ own, other }) => [own ?? 0, other ?? 0]));
    return RINGS.map(({ key, label }, index) => ({
      key,
      label,
      percent: percents[index].own,
      width: (percents[index].own ?? 0) / most,
      otherPercent: percents[index].other,
      otherWidth: (percents[index].other ?? 0) / most,
    }));
  });

  private other(figure: (statistics: OverallStatisticsDto) => number | null): number | null {
    const other = this.comparison()?.statistics;
    return other ? figure(other) : null;
  }
}

function winRate({ wins, gamesWithOpponent }: OverallStatisticsDto): number | null {
  return share(wins, gamesWithOpponent);
}

function missRate({ misses, darts }: OverallStatisticsDto): number | null {
  return share(misses, darts);
}

function locatedRate({ located, darts }: OverallStatisticsDto): number | null {
  return share(located, darts);
}

/** `part` of `whole` in percent; null without a whole. */
function share(part: number, whole: number): number | null {
  return whole === 0 ? null : (100 * part) / whole;
}
