import { formatNumber } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  LOCALE_ID,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { AccuracySummaryDto, FailureCountDto } from '../../dto/accuracy.dto';
import {
  BAND_COLORS,
  ChartGroup,
  FAILURE_LABELS,
  FIELD_LABELS,
  OUTCOMES,
  STRIPE_NAMES,
  bandLabel,
  countsOf,
  failureColor,
  outcomeParts,
  partSeries,
} from '../../models/chart-parts';
import { BarChartComponent, BarRow, BarSeries } from '../bar-chart/bar-chart.component';

/** A dart count as a bar's tip. */
function darts(count: number): string {
  return $localize`:@@eval.dartCount:${count}:count: Darts`;
}

/** The analysis charts with one bar per group, each bar stacked as the chart's rows are
 * when the darts are not grouped. */
@Component({
  selector: 'app-group-charts',
  imports: [BarChartComponent],
  templateUrl: './group-charts.component.html',
  styleUrl: './group-charts.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GroupChartsComponent {
  private readonly locale = inject(LOCALE_ID);

  /** Every grouped game together. */
  readonly summary = input.required<AccuracySummaryDto>();
  readonly failures = input.required<readonly FailureCountDto[]>();
  readonly groups = input.required<readonly ChartGroup[]>();

  protected readonly titles = {
    outcomes: $localize`:@@eval.outcomes:Fehleraufschlüsselung`,
    fields: $localize`:@@eval.byField:Fehler nach Feld`,
    offBy: $localize`:@@eval.offBy:Abstand zum erwarteten Segment`,
    failures: $localize`:@@eval.failures:Leere Erkennungen`,
  };
  protected readonly axes = {
    dartShare: $localize`:@@eval.axis.dartShare:Anteil der Darts`,
    fieldShare: $localize`:@@eval.axis.fieldShare:Anteil der Darts im Feld`,
    offByShare: $localize`:@@eval.axis.offByShare:Anteil der falsch gewerteten Darts`,
    images: $localize`:@@eval.axis.images:Bilder`,
  };

  protected readonly outcomeSeries = partSeries(STRIPE_NAMES, OUTCOMES);
  protected readonly fieldSeries = partSeries(STRIPE_NAMES, ['correct', 'wrong', 'missed']);
  /** The field series switched off, shared by every field's chart. */
  protected readonly fieldHidden = signal<ReadonlySet<number>>(new Set());

  /** Each group's judged darts, phantoms included, as shares of its bar. */
  protected readonly outcomeRows = computed<BarRow[]>(() =>
    this.groups().flatMap(({ label, summary }) => {
      const parts = outcomeParts(countsOf(summary));
      const judged = parts.reduce((sum, part) => sum + part, 0);
      if (judged === 0) {
        return [];
      }
      return {
        label,
        values: parts.map((part) => (100 * part) / judged),
        tip: darts(judged),
        tooltip: [this.games(summary.games)],
      };
    }),
  );

  /** One chart per kind of field, with a bar for each group that threw a dart at it. */
  protected readonly fieldCharts = computed(() =>
    this.summary()
      .fields.map(({ kind }) => ({
        kind,
        label: FIELD_LABELS[kind],
        rows: this.groups().flatMap(({ label, summary }) => {
          const field = summary.fields.find((entry) => entry.kind === kind);
          if (!field?.thrown) {
            return [];
          }
          const share = this.percent(field.thrown, summary.dartsThrown);
          return {
            label,
            values: outcomeParts(field).map((count) => (100 * count) / field.thrown),
            tip: darts(field.thrown),
            tooltip: [$localize`:@@eval.fieldShare:${share}:share: aller geworfenen Darts`],
          };
        }),
      }))
      .filter((chart) => chart.rows.length > 0),
  );

  protected readonly bandSeries = computed<BarSeries[]>(() =>
    this.summary().bands.map((band, index) => ({
      label: bandLabel(band.label),
      color: BAND_COLORS[index] ?? BAND_COLORS[BAND_COLORS.length - 1],
    })),
  );

  /** Each group's located mis-scored darts, split by how far off they landed. */
  protected readonly offByRows = computed<BarRow[]>(() =>
    this.groups().flatMap(({ label, summary }) => {
      const total = summary.bands.reduce((sum, band) => sum + band.darts, 0);
      if (total === 0) {
        return [];
      }
      return {
        label,
        values: summary.bands.map((band) => (100 * band.darts) / total),
        tip: darts(total),
        tooltip: [`Ø ${this.mm(summary.meanOffBy)}`, `Median ${this.mm(summary.medianOffBy)}`],
      };
    }),
  );

  /** Every failure that occurred, in the fixed order that gives each its colour. */
  private readonly failureKeys = computed(() => {
    const seen = new Set(this.groups().flatMap((group) => group.failures.map((f) => f.failure)));
    const known = Object.keys(FAILURE_LABELS);
    return [...seen].sort((a, b) => rank(known, a) - rank(known, b));
  });

  protected readonly failureSeries = computed<BarSeries[]>(() =>
    this.failureKeys().map((failure) => ({
      label: FAILURE_LABELS[failure] ?? failure,
      color: failureColor(failure),
    })),
  );

  /** Each group's empty detections, stacked by why they came back empty. */
  protected readonly failureRows = computed<BarRow[]>(() => {
    const keys = this.failureKeys();
    return this.groups().map(({ label, failures }) => {
      const counts = keys.map((key) => failures.find((f) => f.failure === key)?.count ?? 0);
      const total = counts.reduce((sum, count) => sum + count, 0);
      return {
        label,
        values: counts,
        tip: $localize`:@@eval.imageCount:${total}:count: Bilder`,
        tooltip: keys.flatMap((key, index) =>
          counts[index] ? [`${FAILURE_LABELS[key] ?? key}: ${counts[index]}`] : [],
        ),
      };
    });
  });

  /** Whether the failures exist but cannot be split by this grouping. */
  protected readonly failuresUngrouped = computed(
    () => this.failureKeys().length === 0 && this.failures().length > 0,
  );

  private games(count: number): string {
    return count === 1
      ? $localize`:@@eval.gameCountOne:1 Spiel`
      : $localize`:@@eval.gameCount:${count}:count: Spiele`;
  }

  private mm(value: number | null): string {
    return value === null ? '–' : `${formatNumber(value, this.locale, '1.1-1')} mm`;
  }

  private percent(count: number, base: number): string {
    return base === 0 ? '–' : `${formatNumber((100 * count) / base, this.locale, '1.0-1')} %`;
  }
}

/** Known failures in their fixed order, unknown ones after them. */
function rank(known: readonly string[], failure: string): number {
  const index = known.indexOf(failure);
  return index < 0 ? known.length : index;
}
