import { DOCUMENT, formatNumber } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  LOCALE_ID,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SelectButton } from 'primeng/selectbutton';
import { AccuracySummaryDto, FailureCountDto } from '../../dto/accuracy.dto';
import {
  FAILURE_LABELS,
  FIELD_LABELS,
  OUTCOMES,
  STRIPE_NAMES,
  bandLabel,
  countsOf,
  outcomeParts,
  partSeries,
  partsOf,
} from '../../models/chart-parts';
import { OUTCOME_COLORS, OUTCOME_LABELS } from '../../models/outcome-colors';
import { BarChartComponent, BarRow, BarSeries } from '../bar-chart/bar-chart.component';
import { chartTheme } from '../../../../core/charts/models/chart-plugins';

/** How the darts of a set of games, or of one, were judged: by outcome, by field, by distance,
 * and why detections came back empty. */
@Component({
  selector: 'app-accuracy-charts',
  imports: [BarChartComponent, FormsModule, SelectButton],
  templateUrl: './accuracy-charts.component.html',
  styleUrl: './accuracy-charts.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AccuracyChartsComponent {
  private readonly locale = inject(LOCALE_ID);

  readonly summary = input.required<AccuracySummaryDto>();
  readonly failures = input<readonly FailureCountDto[] | null>(null);

  protected readonly titles = {
    outcomes: $localize`:@@eval.outcomes:Fehleraufschlüsselung`,
    fields: $localize`:@@eval.byField:Fehler nach Feld`,
    offBy: $localize`:@@eval.offBy:Abstand zum erwarteten Segment`,
    failures: $localize`:@@eval.failures:Leere Erkennungen`,
  };
  protected readonly axes = {
    darts: 'Darts',
    fieldShare: $localize`:@@eval.axis.fieldShare:Anteil der Darts im Feld`,
    images: $localize`:@@eval.axis.images:Bilder`,
  };
  protected readonly offBySeries: BarSeries[] = [{ label: '', color: OUTCOME_COLORS.wrong }];
  /** Empty detections are no outcome, so they stay neutral. */
  protected readonly failureSeries: BarSeries[] = [
    { label: '', color: chartTheme(inject(DOCUMENT)).muted },
  ];

  /** Whether each field's bar is as long as its darts or spans the full width. */
  protected readonly fieldScale = signal<'darts' | 'share'>('darts');
  protected readonly scaleOptions = [
    { label: 'Darts', value: 'darts' },
    { label: $localize`:@@eval.scale.share:Anteil`, value: 'share' },
  ];

  private readonly counts = computed(() => countsOf(this.summary()));

  /** The striped parts' legend entries, each with its share of the wrong or missed darts,
   * which only the one bar per outcome carries. */
  private readonly stripes = computed(() => {
    const { wrong, wrongRing, missed, missedZeros } = this.counts();
    return [
      $localize`:@@eval.wrongRingShare:${this.percent(wrongRing, wrong)}:share: falscher Ring`,
      $localize`:@@eval.enteredAsZero:${this.percent(missedZeros, missed)}:share: als 0 eingetragen`,
    ] as const;
  });

  protected readonly outcomeSeries = computed(() => partSeries(this.stripes(), OUTCOMES));
  protected readonly fieldSeries = computed(() =>
    partSeries(STRIPE_NAMES, ['correct', 'wrong', 'missed']),
  );

  /** Each outcome as a bar of its darts, phantoms included, in the outcome's colour. */
  protected readonly outcomeRows = computed<BarRow[]>(() => {
    const summary = this.summary();
    const counts = this.counts();
    const parts = outcomeParts(counts);
    const judged = summary.correct + summary.wrong + summary.missed + summary.phantom;
    return OUTCOMES.map((key) => {
      const count = summary[key];
      const tooltip = [$localize`:@@eval.dartCount:${count}:count: Darts`];
      if (key === 'wrong') {
        const ring = counts.wrongRing;
        tooltip.push($localize`:@@eval.wrongRingOf:davon ${ring}:count: falscher Ring`);
      } else if (key === 'missed') {
        const zeros = counts.missedZeros;
        tooltip.push($localize`:@@eval.missedZerosOf:davon ${zeros}:count: als 0 eingetragen`);
      }
      return {
        label: OUTCOME_LABELS[key],
        values: partsOf(key, parts),
        tip: this.percent(count, judged),
        tooltip,
      };
    });
  });

  /** Each kind of field the thrown darts belonged in, split by how they were judged: as long
   * as its darts, or each over the full width. */
  protected readonly fieldRows = computed<BarRow[]>(() => {
    const summary = this.summary();
    const share = this.fieldScale() === 'share';
    return summary.fields
      .filter((field) => field.thrown > 0)
      .map((field) => {
        const { thrown } = field;
        const parts = outcomeParts(field);
        const ofAll = this.percent(thrown, summary.dartsThrown);
        const count = $localize`:@@eval.dartCount:${thrown}:count: Darts`;
        return {
          label: FIELD_LABELS[field.kind],
          values: share ? parts.map((part) => (100 * part) / thrown) : parts,
          tip: share ? count : ofAll,
          tooltip: [
            share ? $localize`:@@eval.fieldShare:${ofAll}:share: aller geworfenen Darts` : count,
          ],
        };
      });
  });

  /** How far the mis-scored darts with a located tip landed from their segment. */
  protected readonly offByRows = computed<BarRow[]>(() => {
    const bands = this.summary().bands;
    const total = bands.reduce((sum, band) => sum + band.darts, 0);
    return bands.map(({ label, darts }) => ({
      label: bandLabel(label),
      values: [darts],
      tip: this.percent(darts, total),
      tooltip: [$localize`:@@eval.dartCount:${darts}:count: Darts`],
    }));
  });

  /** Why detections came back empty, most common first. */
  protected readonly failureRows = computed<BarRow[]>(() => {
    const failures = this.failures() ?? [];
    const total = failures.reduce((sum, failure) => sum + failure.count, 0);
    return failures.map(({ failure, count }) => ({
      label: FAILURE_LABELS[failure] ?? failure,
      values: [count],
      tip: this.percent(count, total),
      tooltip: [$localize`:@@eval.imageCount:${count}:count: Bilder`],
    }));
  });

  /** Mean, median and largest distance, shown above the bands. */
  protected readonly offByNotes = computed(() => {
    const { meanOffBy, medianOffBy, worstOffBy } = this.summary();
    const mm = (value: number | null) =>
      value === null ? '–' : `${formatNumber(value, this.locale, '1.1-1')} mm`;
    return [`Ø ${mm(meanOffBy)}`, `Median ${mm(medianOffBy)}`, `max ${mm(worstOffBy)}`];
  });

  private percent(count: number, base: number): string {
    return base === 0 ? '–' : `${formatNumber((100 * count) / base, this.locale, '1.0-1')} %`;
  }
}
