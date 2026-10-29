import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MissDirection } from '../../dto/double-statistics.dto';
import { MISS_DIRECTION_LABELS } from '../../models/miss-direction';

const DIRECTIONS: readonly MissDirection[] = ['long', 'short', 'left', 'right'];

/** A double turned to the top with an arrow and share for each way the darts missed it. */
@Component({
  selector: 'app-miss-directions',
  imports: [DecimalPipe],
  templateUrl: './miss-directions.component.html',
  styleUrl: './miss-directions.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MissDirectionsComponent {
  /** Each direction's share of the misses, 0 to 1. */
  readonly shares = input.required<Readonly<Record<MissDirection, number>>>();

  protected readonly labels = MISS_DIRECTION_LABELS;

  protected readonly ariaLabel = computed(() => {
    const shares = this.shares();
    const parts = DIRECTIONS.map(
      (direction) => `${this.labels[direction]} ${Math.round(shares[direction] * 100)} %`,
    );
    return `Daneben geworfen: ${parts.join(', ')}`;
  });
}
