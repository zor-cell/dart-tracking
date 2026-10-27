import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { DartDto } from '../../dto/dart.dto';
import { fieldOutline } from '../../models/board-face';
import { dartColor } from '../../models/dart-colors';
import { fieldName } from '../../models/field-label';
import { FieldFramesComponent } from '../field-frames/field-frames.component';
import { HeatBoardComponent, HeatField } from '../heat-board/heat-board.component';

/** Fill opacity of the miss tile at the least and the most darts, as on the board. */
const MIN_OPACITY = 0.2;
const MAX_OPACITY = 0.9;

/** Label of a dart that hit no field. */
const MISS = '0';

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

  protected readonly pinned = signal<string | null>(null);
  protected readonly hovered = signal<string | null>(null);

  protected readonly total = computed(() =>
    [...this.counts().values()].reduce((sum, count) => sum + count, 0),
  );

  /** The highest count on a board field, the dark end of the scale; misses stay out. */
  protected readonly most = computed(() =>
    Math.max(
      1,
      ...[...this.counts()].filter(([label]) => label !== MISS).map(([, count]) => count),
    ),
  );

  protected readonly fields = computed<HeatField[]>(() =>
    [...this.counts()]
      .filter(([label]) => label !== MISS)
      .map(([label, count]) => ({
        label,
        share: count / this.most(),
        ariaLabel: `${fieldName(label)}: ${count} ${count === 1 ? 'Dart' : 'Darts'}`,
      })),
  );

  protected readonly misses = computed(() => this.counts().get(MISS) ?? 0);
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
      .map(([label, count]) => `${fieldName(label)} ${count}-mal`)
      .join(', ');
    return `Dartscheibe mit ${this.total()} Darts nach Feld. ${top}`;
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
