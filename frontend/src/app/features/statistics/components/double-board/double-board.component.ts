import { ChangeDetectionStrategy, Component, computed, input, model } from '@angular/core';
import { BoardFaceComponent } from '../../../game/components/board-face/board-face.component';
import { BOARD_VIEW_BOX, fieldOutline } from '../../../game/models/board-face';
import { fieldName } from '../../../game/models/field-label';
import { DoubleStatisticsDto } from '../../dto/double-statistics.dto';

/** Fill opacity of a double never hit and of the best hit one. */
const MIN_OPACITY = 0.2;
const MAX_OPACITY = 0.9;

/** The finishing doubles on the board, tinted by how often they were hit; a tap picks one. */
@Component({
  selector: 'app-double-board',
  imports: [BoardFaceComponent],
  templateUrl: './double-board.component.html',
  styleUrl: './double-board.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DoubleBoardComponent {
  readonly doubles = input.required<readonly DoubleStatisticsDto[]>();
  /** Label of the picked double. */
  readonly selected = model<string | null>(null);

  protected readonly viewBox = BOARD_VIEW_BOX;

  protected readonly fields = computed(() => {
    const doubles = this.doubles();
    const best = Math.max(...doubles.map((double) => double.hits / double.attempts));
    return doubles.map((double) => {
      const rate = double.hits / double.attempts;
      return {
        label: double.label,
        d: fieldOutline(double.label, 0) ?? '',
        opacity: MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * (best === 0 ? 0 : rate / best),
        name: `${fieldName(double.label)}: ${double.hits} von ${double.attempts} getroffen`,
      };
    });
  });

  protected readonly outline = computed(() => {
    const label = this.selected();
    return label === null ? null : fieldOutline(label, 0);
  });

  /** A tap on a double thrown at picks it; anywhere else leaves the pick. */
  protected onBoardClick(event: MouseEvent): void {
    const label = (event.target as Element).getAttribute('data-label');
    if (label !== null && this.doubles().some((double) => double.label === label)) {
      this.selected.set(label);
    }
  }
}
