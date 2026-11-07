import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { DartOutcome, TipDto } from '../../dto/accuracy.dto';
import { calledOut } from '../../models/called-out';
import { OUTCOME_COLORS, OUTCOME_LABELS } from '../../models/outcome-colors';
import { BoardFaceComponent } from '../../../game/components/board-face/board-face.component';
import {
  BOARD_BACKING_RADIUS,
  boardViewBox,
  fieldOutline,
  offBoardArrowPath,
  offBoardMark,
} from '../../../game/models/board-face';
import { toSvg } from '../../../game/models/board-geometry';

/** The outcomes a located tip can have, in the legend's order. */
const TIP_OUTCOMES: readonly DartOutcome[] = ['correct', 'wrong', 'phantom'];
/** The order the tips are drawn in, so the wrong ones lie on top. */
const DRAW_ORDER: readonly DartOutcome[] = ['correct', 'phantom', 'wrong'];

/** Half the drawn area in board millimetres, wide like the doubles view. */
const VIEW_EXTENT = 260;
/** Radius of a drawn tip, in board millimetres. */
const TIP_RADIUS = 4;

/** A tip as drawn in its outcome's colour: a dot at its SVG position, or, off the board,
 * an arrow on the margin ring placed by `transform`. */
export interface TipMark {
  readonly x: number;
  readonly y: number;
  readonly color: string;
  readonly transform: string | null;
}

/** The tips of the shown outcomes as marks, correct first and wrong last, as the live
 * board marks them. */
export function tipMarks(tips: readonly TipDto[], hidden: ReadonlySet<DartOutcome>): TipMark[] {
  return DRAW_ORDER.filter((outcome) => !hidden.has(outcome)).flatMap((outcome) =>
    tips
      .filter((tip) => tip.outcome === outcome)
      .map((tip) => {
        const [x, y] = toSvg(tip.x, tip.y);
        const color = OUTCOME_COLORS[outcome];
        if (Math.hypot(x, y) <= BOARD_BACKING_RADIUS) {
          return { x, y, color, transform: null };
        }
        const mark = offBoardMark(x, y);
        const transform = `translate(${mark.x.toFixed(2)} ${mark.y.toFixed(2)}) rotate(${mark.angle.toFixed(2)})`;
        return { x, y, color, transform };
      }),
  );
}

/** Located tips per outcome, on the whole board or booked in one field (as the board names it). */
export function outcomeCounts(
  tips: readonly TipDto[],
  field: string | null,
): Record<DartOutcome, number> {
  const counts: Record<DartOutcome, number> = { correct: 0, wrong: 0, missed: 0, phantom: 0 };
  for (const tip of tips) {
    if (field === null || calledOut(tip.tracked) === field) {
      counts[tip.outcome]++;
    }
  }
  return counts;
}

/** Every located tip as a small dot in its outcome's colour; a tap on a field narrows the
 * counts to it. */
@Component({
  selector: 'app-error-board',
  imports: [BoardFaceComponent],
  templateUrl: './error-board.component.html',
  styleUrl: './error-board.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ErrorBoardComponent {
  readonly tips = input.required<readonly TipDto[]>();

  /** Outcomes hidden from the board through the legend. */
  protected readonly hidden = signal<ReadonlySet<DartOutcome>>(new Set());
  /** The field picked on the board, as the board names it (20, T20, 25). */
  protected readonly picked = signal<string | null>(null);

  protected readonly viewBox = boardViewBox(VIEW_EXTENT);
  protected readonly tipRadius = TIP_RADIUS;
  protected readonly arrowPath = offBoardArrowPath(TIP_RADIUS);

  protected readonly outline = computed(() => {
    const field = this.picked();
    return field === null ? null : fieldOutline(field, 0);
  });

  /** Each outcome with its colour, name and darts on the board or in the picked field. */
  protected readonly legend = computed(() => {
    const counts = outcomeCounts(this.tips(), this.picked());
    return TIP_OUTCOMES.map((outcome) => ({
      outcome,
      color: OUTCOME_COLORS[outcome],
      label: OUTCOME_LABELS[outcome],
      count: counts[outcome],
      shown: !this.hidden().has(outcome),
    }));
  });

  protected readonly marks = computed(() => tipMarks(this.tips(), this.hidden()));

  protected readonly ariaLabel = computed(() =>
    this.legend()
      .map((entry) => `${entry.label} ${entry.count}`)
      .join(', '),
  );

  protected toggle(outcome: DartOutcome): void {
    this.hidden.update((hidden) => {
      const next = new Set(hidden);
      if (!next.delete(outcome)) {
        next.add(outcome);
      }
      return next;
    });
  }

  /** A tap on a field picks it, a second tap or one beside the fields clears it. */
  protected onBoardClick(event: MouseEvent): void {
    const label = (event.target as Element).getAttribute('data-label');
    this.picked.update((picked) => (label === null || label === picked ? null : label));
  }
}
