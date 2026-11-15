import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, model, signal } from '@angular/core';
import { DartDto } from '../../dto/dart.dto';
import { fieldOutline } from '../../models/board-face';
import { dartColor } from '../../models/dart-colors';
import { fieldName } from '../../models/field-label';
import { dartCount } from '../../models/dart-count';
import { FieldFramesComponent } from '../field-frames/field-frames.component';
import { HeatBoardComponent, HeatField } from '../heat-board/heat-board.component';
import { MISS, heatFields, mostOnBoard } from '../../models/heat-fields';

/** Fill opacity of the miss tile at the least and the most darts, as on the board. */
const MIN_OPACITY = 0.2;
const MAX_OPACITY = 0.9;

/** Every dart counted into the field it hit, tinted by how often; a tap or hover names the count. */
@Component({
  selector: 'app-field-heatmap',
  imports: [DecimalPipe, FieldFramesComponent, HeatBoardComponent],
  templateUrl: './field-heatmap.component.html',
  styleUrl: './field-heatmap.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FieldHeatmapComponent {
  /** Darts per field so far, keyed by called-out label. */
  readonly counts = input.required<ReadonlyMap<string, number>>();
  /** The visit under way, in throwing order, framed in each dart's colour. */
  readonly current = input<readonly DartDto[]>([]);

  protected readonly miss = MISS;
  protected readonly dartCount = dartCount;

  /** The field last tapped; bound by a view that keeps it across layers. */
  readonly pinned = model<string | null>(null);
  protected readonly hovered = signal<string | null>(null);

  protected readonly total = computed(() =>
    [...this.counts().values()].reduce((sum, count) => sum + count, 0),
  );

  protected readonly most = computed(() => mostOnBoard(this.counts()));

  protected readonly fields = computed<HeatField[]>(() => heatFields(this.counts(), this.most()));

  protected readonly misses = computed(() => this.counts().get(MISS) ?? 0);
  protected readonly missLabel = computed(
    () => $localize`:@@game.heatmap.missLabel:Daneben: ${dartCount(this.misses())}:darts:`,
  );
  protected readonly missOpacity = computed(() => {
    const misses = this.misses();
    const share = Math.min(1, misses / this.most());
    return misses === 0 ? 0 : MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * Math.sqrt(share);
  });

  /** Ordinals of the visit's darts that missed, shown beside the miss tile. */
  protected readonly missOrdinals = computed(() =>
    this.current().flatMap((dart, index) =>
      dart.label === MISS ? [{ value: index + 1, color: dartColor(index) }] : [],
    ),
  );

  /** The field under the pointer or last tapped, hit or not. */
  protected readonly selected = computed(() => {
    const label = this.hovered() ?? this.pinned();
    if (label === null || (label !== MISS && fieldOutline(label, 0) === null)) {
      return null;
    }
    const count = this.counts().get(label) ?? 0;
    return {
      label,
      count,
      name: fieldName(label),
      share: (count / Math.max(1, this.total())) * 100,
    };
  });

  protected readonly ariaLabel = computed(() => {
    const top = [...this.counts()]
      .filter(([label]) => label !== MISS)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([label, count]) => $localize`:@@game.heatmap.times:${fieldName(label)}:field: ${count}:count:-mal`)
      .join(', ');
    return $localize`:@@game.heatmap.fieldsLabel:Dartscheibe mit ${this.total()}:count: Darts nach Feld. ${top}:top:`;
  });

  protected toggleMiss(): void {
    this.pinned.update((pinned) => (pinned === MISS ? null : MISS));
  }

  protected onMissEnter(event: PointerEvent): void {
    if (event.pointerType === 'mouse') {
      this.hovered.set(MISS);
    }
  }
}
