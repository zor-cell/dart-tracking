import { DartOutcome } from '../dto/accuracy.dto';
import { SERIES_COLORS } from '../../../core/charts/models/series-colors';

/** Each outcome's colour, the same in every chart and on the board; red and orange differ in lightness too. */
export const OUTCOME_COLORS: Record<DartOutcome, string> = {
  correct: '#22a845',
  wrong: '#c42b2b',
  missed: '#f59a3c',
  phantom: SERIES_COLORS[6],
};

/** A mis-scored dart whose tip a correction moved into its field. */
export const SNAPPED_COLOR = SERIES_COLORS[0];

/** What the outcomes are called on the page, in reading order. */
export const OUTCOME_LABELS: Record<DartOutcome, string> = {
  correct: $localize`:@@eval.correct:Korrekt`,
  wrong: $localize`:@@eval.wrong:Falsch`,
  missed: $localize`:@@eval.missed:Verpasst`,
  phantom: $localize`:@@eval.phantom:Phantom`,
};
