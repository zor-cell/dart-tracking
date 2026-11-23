import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { AccuracySummaryDto, GameAccuracyDto, TipDto } from '../../dto/accuracy.dto';
import { ErrorBoardComponent } from '../error-board/error-board.component';

/** The headline figures of a set of games, or of one with its recording, and where the camera
 * put the darts; projects the trend between them. */
@Component({
  selector: 'app-accuracy-summary',
  imports: [DecimalPipe, ErrorBoardComponent],
  templateUrl: './accuracy-summary.component.html',
  styleUrl: './accuracy-summary.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AccuracySummaryComponent {
  readonly summary = input.required<AccuracySummaryDto>();
  /** A single game, whose tracker version and camera angle are shown with its figures. */
  readonly game = input<GameAccuracyDto | null>(null);
  /** Every located tip, drawn on a board in its outcome's colour. */
  readonly tips = input<readonly TipDto[] | null>(null);

  /** Share of thrown darts booked in the right segment. */
  protected readonly accuracy = computed(() => {
    const summary = this.summary();
    return summary.dartsThrown === 0 ? null : summary.correct / summary.dartsThrown;
  });

  protected readonly cleanVisitRate = computed(() => {
    const summary = this.summary();
    return summary.visits === 0 ? null : summary.cleanVisits / summary.visits;
  });

  protected readonly sides = {
    left: $localize`:@@eval.left:links`,
    right: $localize`:@@eval.right:rechts`,
    below: $localize`:@@eval.below:unterhalb`,
    above: $localize`:@@eval.above:oberhalb`,
  };

  protected sideOf(degrees: number, negative: string, positive: string): string {
    return `${Math.round(Math.abs(degrees))}° ${degrees < 0 ? negative : positive}`;
  }
}
