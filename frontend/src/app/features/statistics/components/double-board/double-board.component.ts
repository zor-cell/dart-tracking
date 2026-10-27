import { DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, model, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SelectButton } from 'primeng/selectbutton';
import {
  HeatBoardComponent,
  HeatField,
} from '../../../game/components/heat-board/heat-board.component';
import { TipHeatmapComponent } from '../../../game/components/tip-heatmap/tip-heatmap.component';
import { fieldOutline } from '../../../game/models/board-face';
import { fieldName } from '../../../game/models/field-label';
import {
  HEATMAP_LAYERS,
  HeatmapLayer,
  storeHeatmapLayer,
  storedHeatmapLayer,
} from '../../../game/models/heatmap-layer';
import { TipPoint } from '../../../game/models/tip-density';
import { DoubleStatisticsDto } from '../../dto/double-statistics.dto';

/** The darts thrown at a finishing double, as a tip cloud or as each double's hit rate;
 * a tap on a double narrows both to it. */
@Component({
  selector: 'app-double-board',
  imports: [
    DecimalPipe,
    FormsModule,
    HeatBoardComponent,
    NgTemplateOutlet,
    SelectButton,
    TipHeatmapComponent,
  ],
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

  protected readonly selectable = (label: string): boolean =>
    this.doubles().some((double) => double.label === label);

  private readonly best = computed(() =>
    Math.max(0, ...this.doubles().map((double) => double.hits / double.attempts)),
  );

  protected readonly attempts = computed(() =>
    this.doubles().reduce((sum, double) => sum + double.attempts, 0),
  );

  protected readonly fields = computed<HeatField[]>(() =>
    this.doubles().map((double) => ({
      label: double.label,
      share: this.best() === 0 ? 0 : double.hits / double.attempts / this.best(),
      ariaLabel: `${fieldName(double.label)}: ${double.hits} von ${double.attempts} getroffen`,
    })),
  );

  protected readonly legendMax = computed(() => `${Math.round(this.best() * 100)} %`);

  /** Where the darts at the picked double landed, or at every double without a pick. */
  protected readonly tips = computed<TipPoint[]>(() => {
    const picked = this.selected();
    return this.doubles()
      .filter((double) => picked === null || double.label === picked)
      .flatMap((double) => double.throws.map(([x, y]) => [x, y] as const));
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

  /** The double under the pointer or picked, with its rate. */
  protected readonly shown = computed(() => {
    const label = this.hovered() ?? this.selected();
    const double = this.doubles().find((entry) => entry.label === label);
    return double
      ? { ...double, name: fieldName(double.label), rate: double.hits / double.attempts }
      : null;
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

  protected onTargetEnter(label: string, event: PointerEvent): void {
    if (event.pointerType === 'mouse') {
      this.hovered.set(label);
    }
  }
}
