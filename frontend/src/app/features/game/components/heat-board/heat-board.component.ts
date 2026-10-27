import { ChangeDetectionStrategy, Component, computed, input, model } from '@angular/core';
import { BOARD_VIEW_BOX, fieldOutline } from '../../models/board-face';
import { BoardFaceComponent, FieldEnter } from '../board-face/board-face.component';
import { HeatLegendComponent } from '../heat-legend/heat-legend.component';

/** One tinted field: `share` is its value against the highest, 0 to 1. */
export interface HeatField {
  readonly label: string;
  readonly share: number;
  readonly ariaLabel: string;
}

/** Fill opacity of the least and the most valued field. */
const MIN_OPACITY = 0.2;
const MAX_OPACITY = 0.9;

/**
 * A board with fields tinted by value, a picked field outlined, the caption top left and the
 * scale bottom right. Projects `[caption]`, `[corner]` (bottom left) and `svg:g[overlay]`.
 */
@Component({
  selector: 'app-heat-board',
  imports: [BoardFaceComponent, HeatLegendComponent],
  templateUrl: './heat-board.component.html',
  styleUrl: './heat-board.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[style.--heat-fill]': 'fill()' },
})
export class HeatBoardComponent {
  readonly fields = input.required<readonly HeatField[]>();
  readonly ariaLabel = input.required<string>();
  /** CSS colour the fields are tinted in. */
  readonly fill = input('var(--p-text-color)');
  /** Opacity for a share; the square root by default keeps one high value from washing out the rest. */
  readonly scale = input<(share: number) => number>(
    (share) => MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * Math.sqrt(share),
  );
  /** Whether a tap or hover on `label` may pick it. */
  readonly selectable = input<(label: string) => boolean>(() => true);
  /** What the top of the scale reads; no scale without it. */
  readonly legendMax = input<string | null>(null);

  /** The field last tapped or focused. */
  readonly selected = model<string | null>(null);
  /** The field under the mouse. */
  readonly hovered = model<string | null>(null);

  protected readonly viewBox = BOARD_VIEW_BOX;

  protected readonly paths = computed(() =>
    this.fields().flatMap((field) => {
      const d = fieldOutline(field.label, 0);
      return d === null ? [] : [{ ...field, d, opacity: this.opacity(field.share) }];
    }),
  );

  protected readonly outline = computed(() => {
    const label = this.hovered() ?? this.selected();
    return label === null ? null : fieldOutline(label, 0);
  });

  protected readonly legendColor = (share: number): string =>
    `color-mix(in srgb, ${this.fill()} ${(this.scale()(share) * 100).toFixed(0)}%, transparent)`;

  private opacity(share: number): number {
    return share <= 0 ? 0 : this.scale()(Math.min(1, share));
  }

  /** A tap on a pickable field picks it, a second tap or one beside the fields clears it. */
  protected onBoardClick(event: MouseEvent): void {
    const label = (event.target as Element).getAttribute('data-label');
    if (label !== null && !this.selectable()(label)) {
      return;
    }
    this.selected.update((pinned) => (label === null || label === pinned ? null : label));
  }

  protected onFieldEnter({ event, label }: FieldEnter): void {
    if (event.pointerType === 'mouse' && this.selectable()(label)) {
      this.hovered.set(label);
    }
  }

  protected onFieldLeave(): void {
    this.hovered.set(null);
  }
}
