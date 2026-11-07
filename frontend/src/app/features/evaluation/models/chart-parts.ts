import {
  AccuracySummaryDto,
  DartOutcome,
  FailureCountDto,
  FieldKind,
} from '../dto/accuracy.dto';
import { BarSeries } from '../components/bar-chart/bar-chart.component';
import { OUTCOME_COLORS, OUTCOME_LABELS } from './outcome-colors';
import { SERIES_COLORS } from '../../../core/charts/models/series-colors';

/** One group of the darts, worded for the page. */
export interface ChartGroup {
  readonly label: string;
  readonly summary: AccuracySummaryDto;
  readonly failures: readonly FailureCountDto[];
}

/** The outcomes in reading order. */
export const OUTCOMES: readonly DartOutcome[] = ['correct', 'wrong', 'missed', 'phantom'];

/** The counts a bar splits into, with the striped shares of the wrong and the missed darts. */
export interface OutcomeCounts {
  readonly correct: number;
  readonly wrong: number;
  readonly wrongRing: number;
  readonly missed: number;
  readonly missedZeros: number;
  readonly phantom?: number;
}

/** The parts of `outcomeParts` that belong to each outcome. */
const PARTS: Record<DartOutcome, readonly number[]> = {
  correct: [0],
  wrong: [1, 2],
  missed: [3, 4],
  phantom: [5],
};

/** The stacked parts of a bar: correct, wrong, of those in the wrong ring, missed, of those
 * entered as 0, and phantom. */
export function outcomeParts(counts: OutcomeCounts): number[] {
  const { correct, wrong, wrongRing, missed, missedZeros, phantom = 0 } = counts;
  return [correct, wrong - wrongRing, wrongRing, missed - missedZeros, missedZeros, phantom];
}

/** The parts of one outcome only, the others left at zero. */
export function partsOf(outcome: DartOutcome, parts: readonly number[]): number[] {
  return parts.map((value, index) => (PARTS[outcome].includes(index) ? value : 0));
}

/** A summary's counts, with the wrong darts that only missed the ring. */
export function countsOf(summary: AccuracySummaryDto): OutcomeCounts {
  const wrongRing = summary.fields.reduce((sum, field) => sum + field.wrongRing, 0);
  return { ...summary, wrongRing };
}

/** The striped parts' names, for a legend over several bars. */
export const STRIPE_NAMES = [
  $localize`:@@eval.wrongRing:falscher Ring`,
  $localize`:@@eval.enteredZero:als 0 eingetragen`,
] as const;

/** One series per part, coloured by outcome; the legend shows the striped ones, labelled
 * `stripes`, and the `named` outcomes. */
export function partSeries(
  stripes: readonly [string, string],
  named: readonly DartOutcome[],
): BarSeries[] {
  const part = (key: DartOutcome, label = named.includes(key) ? OUTCOME_LABELS[key] : '') => ({
    label,
    color: OUTCOME_COLORS[key],
  });
  return [
    part('correct'),
    part('wrong'),
    { ...part('wrong', stripes[0]), hatched: true },
    part('missed'),
    { ...part('missed', stripes[1]), hatched: true },
    part('phantom'),
  ];
}

export const FIELD_LABELS: Record<FieldKind, string> = {
  single: 'Single',
  double: 'Double',
  triple: 'Triple',
  outside: $localize`:@@game.miss:Daneben`,
};

/** Why a detection came back empty, worded as the camera badge words it. */
export const FAILURE_LABELS: Readonly<Record<string, string | undefined>> = {
  invalid_image: $localize`:@@detection.invalidImage:Bild nicht lesbar`,
  not_calibrated: $localize`:@@detection.notCalibrated:Erst kalibrieren`,
  alignment_failed: $localize`:@@detection.moved:Kamera hat sich bewegt`,
  no_change: $localize`:@@detection.noThrow:Kein Wurf erkannt`,
  implausible_shape: $localize`:@@detection.covered:Board verdeckt`,
  darts_removed: $localize`:@@detection.removed:Pfeile entfernt`,
};

/** The colour of a failure, fixed by its place among the known ones. */
export function failureColor(failure: string): string {
  const index = Object.keys(FAILURE_LABELS).indexOf(failure);
  return SERIES_COLORS[index < 0 ? SERIES_COLORS.length - 1 : index];
}

/** The distance bands from near to far, light to dark red. */
export const BAND_COLORS = ['#f5bdb6', '#e57a6f', '#c42b2b', '#7a1414'] as const;

/** A band's label as the page writes it: `<= 5 mm` as `≤ 5 mm`, `5 - 20 mm` as `5–20 mm`. */
export function bandLabel(label: string): string {
  return label.replace('<=', '≤').replace(' - ', '–');
}
