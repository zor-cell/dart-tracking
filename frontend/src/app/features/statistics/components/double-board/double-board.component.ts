import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, model, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SelectButton } from 'primeng/selectbutton';
import {
  HeatBoardComponent,
  HeatField,
} from '../../../game/components/heat-board/heat-board.component';
import {
  HeatmapPick,
  TipHeatmapComponent,
} from '../../../game/components/tip-heatmap/tip-heatmap.component';
import { fieldOutline } from '../../../game/models/board-face';
import { SECTOR_ORDER } from '../../../game/models/board-geometry';
import { fieldName, parseField } from '../../../game/models/field-label';
import {
  HEATMAP_LAYERS,
  HeatmapLayer,
  storeHeatmapLayer,
  storedHeatmapLayer,
} from '../../../game/models/heatmap-layer';
import { TipPoint } from '../../../game/models/tip-density';
import { DoubleStatisticsDto, MissDirection } from '../../dto/double-statistics.dto';
import { MISS_DIRECTION_LABELS, missShares } from '../../models/miss-direction';

/** Label of a dart that hit no field. */
const MISS = '0';

const DIRECTIONS: readonly MissDirection[] = ['long', 'short', 'left', 'right'];

/** The darts thrown at a finishing double, as a tip cloud or as each double's hit rate.
 * A picked double narrows both. */
@Component({
  selector: 'app-double-board',
  imports: [DecimalPipe, FormsModule, HeatBoardComponent, SelectButton, TipHeatmapComponent],
  templateUrl: './double-board.component.html',
  styleUrl: './double-board.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DoubleBoardComponent {
  readonly doubles = input.required<readonly DoubleStatisticsDto[]>();
  /** Label of the picked double. */
  readonly selected = model<string | null>(null);

  protected readonly hovered = signal<string | null>(null);
  protected readonly layerOptions = [...HEATMAP_LAYERS];
  protected readonly layer = signal(storedHeatmapLayer());
  protected readonly labels = MISS_DIRECTION_LABELS;
  protected readonly directionOrder = DIRECTIONS;

  /** The double of the sector `label` lies in, the bull for both bull rings; null if never
   * thrown at. */
  protected readonly doubleOf = (label: string): string | null => {
    const field = parseField(label);
    if (field === null) {
      return null;
    }
    const double = 'index' in field ? `D${SECTOR_ORDER[field.index]}` : '50';
    return this.doubles().some((entry) => entry.label === double) ? double : null;
  };

  protected readonly attempts = computed(() =>
    this.doubles().reduce((sum, double) => sum + double.attempts, 0),
  );

  /** What the darts at the picked double hit, or at every double without a pick, tracked or not. */
  private readonly scored = computed(() => {
    const picked = this.picked();
    const counts = new Map<string, number>();
    for (const double of picked ? [picked] : this.doubles()) {
      for (const [label, count] of Object.entries(double.fields)) {
        counts.set(label, (counts.get(label) ?? 0) + count);
      }
    }
    return counts;
  });

  protected readonly misses = computed(() => this.scored().get(MISS) ?? 0);

  /** The highest count on a board field, the dark end of the scale. */
  private readonly most = computed(() =>
    Math.max(1, ...[...this.scored()].filter(([label]) => label !== MISS).map(([, n]) => n)),
  );

  protected readonly fields = computed<HeatField[]>(() =>
    [...this.scored()]
      .filter(([label]) => label !== MISS)
      .map(([label, count]) => ({
        label,
        share: count / this.most(),
        ariaLabel: `${fieldName(label)}: ${count} ${count === 1 ? 'Dart' : 'Darts'}`,
      })),
  );

  protected readonly legendMax = computed(() => `${this.most()}`);

  private readonly picked = computed(
    () => this.doubles().find((double) => double.label === this.selected()) ?? null,
  );

  /** Where the darts at the picked double landed, or at every double without a pick. */
  protected readonly tips = computed<TipPoint[]>(() => {
    const picked = this.picked();
    return (picked ? [picked] : this.doubles()).flatMap((double) =>
      double.throws.map(([x, y]) => [x, y] as const),
    );
  });

  /** Each side's share of the misses: the picked double's, or all doubles' together. */
  protected readonly shares = computed(() => {
    const picked = this.picked();
    const counts = { short: 0, long: 0, left: 0, right: 0 };
    for (const double of picked ? [picked] : this.doubles()) {
      for (const direction of DIRECTIONS) {
        counts[direction] += double.directions[direction];
      }
    }
    return missShares(counts);
  });

  /** Every double as a tap target over the tip cloud, with the hovered or picked one outlined. */
  protected readonly targets = computed(() =>
    this.doubles().map((double) => ({
      label: double.label,
      d: fieldOutline(double.label, 0) ?? '',
      ariaLabel: `${fieldName(double.label)}: ${double.hits} von ${double.attempts} getroffen`,
    })),
  );

  protected readonly outline = computed(() => {
    const label = this.hovered() ?? this.selected();
    return label === null ? null : fieldOutline(label, 0);
  });

  /** The double under the pointer or picked, with its rate over every dart thrown at it. */
  protected readonly shown = computed(() => {
    const label = this.hovered() ?? this.selected();
    const double = this.doubles().find((entry) => entry.label === label);
    return double
      ? { ...double, name: fieldName(double.label), rate: double.hits / double.attempts }
      : null;
  });

  /** The same double on the cloud, its rate over the darts that were located. */
  protected readonly tipPick = computed<HeatmapPick | null>(() => {
    const double = this.shown();
    if (double === null) {
      return null;
    }
    const located = double.throws.length;
    const hits = double.throws.filter(([, , hit]) => hit).length;
    const rate = Math.round((hits / Math.max(1, located)) * 100);
    return {
      name: double.name,
      detail: located === 0 ? 'keine Darts erkannt' : `${hits} / ${located} · ${rate} %`,
    };
  });

  protected selectLayer(layer: HeatmapLayer): void {
    this.layer.set(layer);
    storeHeatmapLayer(layer);
  }

  protected toggle(label: string, event: Event): void {
    event.stopPropagation();
    event.preventDefault();
    this.selected.update((picked) => (picked === label ? null : label));
  }

  /** A tap anywhere in a sector picks its double; a second tap or one off the board clears it. */
  protected pickSegment(event: MouseEvent): void {
    const label = (event.target as Element).getAttribute('data-label');
    const double = label === null ? null : this.doubleOf(label);
    this.selected.update((picked) => (double === null || double === picked ? null : double));
  }

  protected onTargetEnter(label: string, event: PointerEvent): void {
    if (event.pointerType === 'mouse') {
      this.hovered.set(label);
    }
  }
}
