import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { DartDto } from '../../dto/dart.dto';
import { BOARD_VIEW_BOX, fieldOutline } from '../../models/board-face';
import { dartColor } from '../../models/dart-colors';
import { fieldName } from '../../models/field-label';
import { BoardFaceComponent, FieldEnter } from '../board-face/board-face.component';
import { FieldFramesComponent } from '../field-frames/field-frames.component';

/** Fill opacity of the least and the most hit field. */
const MIN_OPACITY = 0.2;
const MAX_OPACITY = 0.9;

/** Points along the legend's gradient, as fractions of the highest count. */
const LEGEND_STOPS = [0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 1];

/** Label of a dart that hit no field. */
const MISS = '0';

/** Every dart counted into the field it hit, tinted by how often; a tap or hover names the count. */
@Component({
  selector: 'app-field-heatmap',
  imports: [BoardFaceComponent, DecimalPipe, FieldFramesComponent],
  templateUrl: './field-heatmap.component.html',
  styleUrl: './field-heatmap.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FieldHeatmapComponent {
  /** Called-out fields of every dart so far, one entry per dart. */
  readonly labels = input.required<readonly string[]>();
  /** The visit under way, in throwing order, framed in each dart's colour. */
  readonly current = input<readonly DartDto[]>([]);

  protected readonly viewBox = BOARD_VIEW_BOX;
  protected readonly miss = MISS;

  private readonly pinned = signal<string | null>(null);
  private readonly hovered = signal<string | null>(null);

  private readonly counts = computed(() => {
    const counts = new Map<string, number>();
    for (const label of this.labels()) {
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
    return counts;
  });

  /** Fill opacity for a count; the square root keeps one heavily hit field from washing out the rest. */
  private readonly opacity = computed(() => {
    const most = this.most();
    return (count: number) =>
      count === 0 ? 0 : MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * Math.sqrt(count / most);
  });

  /** The highest count on any field, the dark end of the scale. */
  protected readonly most = computed(() => Math.max(1, ...this.counts().values()));

  /** The fill scale as a gradient from no hits to the highest count, on the same square root. */
  protected readonly legendGradient = computed(() => {
    const stops = LEGEND_STOPS.map((share) => {
      const opacity = MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * Math.sqrt(share);
      return `color-mix(in srgb, var(--p-text-color) ${(opacity * 100).toFixed(0)}%, transparent) ${share * 100}%`;
    });
    return `linear-gradient(to right, transparent 0%, ${stops.join(', ')})`;
  });

  protected readonly fields = computed(() =>
    [...this.counts()].flatMap(([label, count]) => {
      const d = fieldOutline(label, 0);
      return d === null
        ? []
        : [{ label, d, count, opacity: this.opacity()(count), name: fieldName(label) }];
    }),
  );

  protected readonly misses = computed(() => this.counts().get(MISS) ?? 0);
  protected readonly missOpacity = computed(() => this.opacity()(this.misses()));

  /** Ordinals of the visit's darts that missed, shown beside the miss tile. */
  protected readonly missOrdinals = computed(() =>
    this.current().flatMap((dart, index) =>
      dart.label === MISS ? [{ value: index + 1, color: dartColor(index) }] : [],
    ),
  );

  /** The field under the pointer or last tapped, hit or not. */
  protected readonly selected = computed(() => {
    const label = this.hovered() ?? this.pinned();
    const d = label === null ? null : fieldOutline(label, 0);
    if (label === null || (d === null && label !== MISS)) {
      return null;
    }
    const count = this.counts().get(label) ?? 0;
    return {
      label,
      d,
      count,
      name: fieldName(label),
      share: (count / Math.max(1, this.labels().length)) * 100,
    };
  });

  protected readonly ariaLabel = computed(() => {
    const top = [...this.fields()]
      .sort((a, b) => b.count - a.count)
      .slice(0, 5)
      .map((field) => `${field.name} ${field.count}-mal`)
      .join(', ');
    return `Dartscheibe mit ${this.labels().length} Darts nach Feld. ${top}`;
  });

  /** A tap on a hit field pins its count; a tap anywhere else clears it. */
  protected onBoardClick(event: MouseEvent): void {
    const label = (event.target as Element).getAttribute('data-label');
    this.pinned.update((pinned) => (label === null || label === pinned ? null : label));
  }

  protected onFieldEnter({ event, label }: FieldEnter): void {
    if (event.pointerType === 'mouse') {
      this.hovered.set(label);
    }
  }

  protected onFieldLeave(): void {
    this.hovered.set(null);
  }

  protected onFieldFocus(label: string): void {
    this.pinned.set(label);
  }

  protected toggleMiss(): void {
    this.pinned.update((pinned) => (pinned === MISS ? null : MISS));
  }
}
