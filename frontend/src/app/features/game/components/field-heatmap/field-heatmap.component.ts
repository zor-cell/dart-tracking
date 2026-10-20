import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import {
  BOARD_BACKING_RADIUS,
  BOARD_SECTOR_NUMBERS,
  BOARD_SEGMENTS,
  BOARD_VIEW_BOX,
  fieldLabelPoint,
  fieldOutline,
} from '../../models/board-face';
import { BULLSEYE_RADIUS, BULL_RADIUS } from '../../models/board-geometry';
import { dartColor } from '../../models/dart-colors';

/** Fill opacity of the least and the most hit field. */
const MIN_OPACITY = 0.2;
const MAX_OPACITY = 0.9;

/** Stroke width of a current dart's outline, and how far each further one on the same field moves in. */
const OUTLINE_WIDTH = 3;
const OUTLINE_STEP = 3;

/** Label of a dart that hit no field. */
const MISS = '0';

/** Every dart counted into the field it hit, tinted by how often; a tap or hover names the count. */
@Component({
  selector: 'app-field-heatmap',
  imports: [DecimalPipe],
  templateUrl: './field-heatmap.component.html',
  styleUrl: './field-heatmap.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FieldHeatmapComponent {
  /** Called-out fields of every dart so far, one entry per dart. */
  readonly labels = input.required<readonly string[]>();
  /** Fields of the visit under way, in throwing order, outlined in their dart's colour. */
  readonly current = input<readonly string[]>([]);

  protected readonly segments = BOARD_SEGMENTS;
  protected readonly sectorNumbers = BOARD_SECTOR_NUMBERS;
  protected readonly bullRadius = BULL_RADIUS;
  protected readonly bullseyeRadius = BULLSEYE_RADIUS;
  protected readonly backingRadius = BOARD_BACKING_RADIUS;
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
    const most = Math.max(1, ...this.counts().values());
    return (count: number) =>
      count === 0 ? 0 : MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * Math.sqrt(count / most);
  });

  protected readonly fields = computed(() =>
    [...this.counts()].flatMap(([label, count]) => {
      const d = fieldOutline(label, 0);
      return d === null
        ? []
        : [{ label, d, count, opacity: this.opacity()(count), name: fieldName(label) }];
    }),
  );

  protected readonly outlineWidth = OUTLINE_WIDTH;
  protected readonly outlines = computed(() => {
    const seen = new Map<string, number>();
    return this.current().flatMap((label, index) => {
      const before = seen.get(label) ?? 0;
      seen.set(label, before + 1);
      const d = fieldOutline(label, OUTLINE_WIDTH / 2 + before * OUTLINE_STEP);
      return d === null ? [] : [{ d, color: dartColor(index) }];
    });
  });

  protected readonly misses = computed(() => this.counts().get(MISS) ?? 0);
  protected readonly missOpacity = computed(() => this.opacity()(this.misses()));

  /** Ordinals of the visit's darts that missed, shown beside the miss tile. */
  protected readonly missOrdinals = computed(() =>
    this.current().flatMap((label, index) =>
      label === MISS ? [{ value: index + 1, color: dartColor(index) }] : [],
    ),
  );

  /** The visit's ordinals per field, written where the field has room, each in its dart's colour. */
  protected readonly ordinals = computed(() => {
    const fields = new Map<
      string,
      { x: number; y: number; values: { value: number; color: string }[] }
    >();
    this.current().forEach((label, index) => {
      const point = fieldLabelPoint(label);
      if (point === null) {
        return;
      }
      const field = fields.get(label) ?? { x: point[0], y: point[1], values: [] };
      field.values.push({ value: index + 1, color: dartColor(index) });
      fields.set(label, field);
    });
    return [...fields.values()];
  });

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

  protected onFieldEnter(event: PointerEvent, label: string): void {
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

/** How a field is named in the caption: T20, D16, 20, Bull, Double Bull, Daneben. */
function fieldName(label: string): string {
  if (label === MISS) {
    return 'Daneben';
  }
  return label === '50' ? 'Double Bull' : label === '25' ? 'Bull' : label;
}
