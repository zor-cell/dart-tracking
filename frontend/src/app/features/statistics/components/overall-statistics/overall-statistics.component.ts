import {
  DOCUMENT,
  DatePipe,
  DecimalPipe,
  NgTemplateOutlet,
  formatDate,
  formatNumber,
} from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  LOCALE_ID,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { ChartData, ChartOptions } from 'chart.js';
import { UIChart } from 'primeng/chart';
import { SelectButton } from 'primeng/selectbutton';
import { chartTheme } from '../../../../core/charts/models/chart-plugins';
import { axisTicks, tooltipStyle } from '../../../../core/charts/models/chart-styles';
import { SHORT_DATE } from '../../../../core/i18n/models/date-format';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { FieldHeatmapComponent } from '../../../game/components/field-heatmap/field-heatmap.component';
import { TipHeatmapComponent } from '../../../game/components/tip-heatmap/tip-heatmap.component';
import { GameVariant } from '../../../game/models/game-variant';
import {
  HEATMAP_LAYERS,
  HeatmapLayer,
  storeHeatmapLayer,
  storedHeatmapLayer,
} from '../../../game/models/heatmap-layer';
import { OverallStatisticsDto } from '../../dto/overall-statistics.dto';
import { OWN_COLOR } from '../../models/comparison';
import { STATISTICS_GAMES, StatisticsGame, variantLabel } from '../../models/statistics-game';

/** One bar of a list: its name, its count and its length against the longest. */
interface BarRow {
  readonly key: string;
  readonly label: string;
  readonly count: number;
  readonly share: number;
  readonly figure: string;
  /** The game the row opens; null for one without figures of its own. */
  readonly game: StatisticsGame | null;
}

/** The rings, the 25 counted as a single and the bull as a double. */
const RINGS: readonly { key: string; label: string }[] = [
  { key: 'single', label: 'Single' },
  { key: 'double', label: 'Double' },
  { key: 'triple', label: 'Triple' },
  { key: 'miss', label: $localize`:@@game.miss:Daneben` },
];

/** Every game of any kind: how much was played, where the darts went, when and against whom. */
@Component({
  selector: 'app-overall-statistics',
  imports: [
    DatePipe,
    DecimalPipe,
    FieldHeatmapComponent,
    FormsModule,
    InfoHintComponent,
    NgTemplateOutlet,
    SelectButton,
    TipHeatmapComponent,
    UIChart,
  ],
  templateUrl: './overall-statistics.component.html',
  styleUrl: './overall-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OverallStatisticsComponent {
  private readonly locale = inject(LOCALE_ID);
  private readonly theme = chartTheme(inject(DOCUMENT));

  readonly statistics = input.required<OverallStatisticsDto>();
  /** A game picked from the list by kind, to show its own figures. */
  readonly pick = output<StatisticsGame>();

  protected readonly shortDate = SHORT_DATE;
  protected readonly layerOptions = [...HEATMAP_LAYERS];
  protected readonly layer = signal(storedHeatmapLayer());
  protected readonly pinnedField = signal<string | null>(null);

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

  protected readonly variants = computed<BarRow[]>(() => {
    const entries = Object.entries(this.statistics().variants).sort(([, a], [, b]) => b - a);
    const most = Math.max(1, ...entries.map(([, count]) => count));
    return entries.map(([variant, count]) => ({
      key: variant,
      label: variantLabel(variant as GameVariant),
      count,
      share: count / most,
      figure:
        count === 1
          ? $localize`:@@stats.all.oneGame:1 Spiel`
          : $localize`:@@stats.all.games:${count}:count: Spiele`,
      game: STATISTICS_GAMES.find((option) => option.value === variant)?.value ?? null,
    }));
  });

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
        game: null,
      };
    });
  });

  protected readonly fieldCounts = computed(() => new Map(Object.entries(this.statistics().fields)));
  protected readonly tipCounts = computed(
    () => new Map(Object.entries(this.statistics().locatedFields)),
  );

  protected readonly weeksData = computed<ChartData<'bar'>>(() => ({
    labels: this.statistics().weeks.map((week) => formatDate(week.week, SHORT_DATE, this.locale)),
    datasets: [
      {
        data: this.statistics().weeks.map((week) => week.darts),
        backgroundColor: OWN_COLOR,
        borderRadius: 2,
      },
    ],
  }));

  protected readonly weeksOptions = computed<ChartOptions<'bar'>>(() => {
    const theme = this.theme;
    return {
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltipStyle(theme),
          displayColors: false,
          callbacks: {
            title: (items) => $localize`:@@stats.all.weekOf:Woche ab ${items[0]?.label ?? ''}:date:`,
            label: (item) => `${formatNumber(item.parsed.y ?? 0, this.locale, '1.0-0')} Darts`,
          },
        },
      },
      scales: {
        x: { ticks: { ...axisTicks(theme), maxTicksLimit: 5, maxRotation: 0 }, grid: { display: false } },
        y: { beginAtZero: true, ticks: axisTicks(theme), grid: { color: theme.border } },
      },
    };
  });

  protected selectLayer(layer: HeatmapLayer): void {
    this.layer.set(layer);
    storeHeatmapLayer(layer);
  }
}

/** `part` of `whole` in percent; null without a whole. */
function share(part: number, whole: number): number | null {
  return whole === 0 ? null : (100 * part) / whole;
}

/** A time span read the way people say it: 31 h, 4,5 h, 13 min. */
function duration(seconds: number, locale: string): string {
  const hours = seconds / 3600;
  if (hours >= 1) {
    return `${formatNumber(hours, locale, hours < 10 ? '1.0-1' : '1.0-0')} h`;
  }
  return `${formatNumber(seconds / 60, locale, '1.0-0')} min`;
}
