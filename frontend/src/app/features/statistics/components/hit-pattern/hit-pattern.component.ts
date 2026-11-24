import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SelectButton } from 'primeng/selectbutton';
import { FieldHeatmapComponent } from '../../../game/components/field-heatmap/field-heatmap.component';
import { TipHeatmapComponent } from '../../../game/components/tip-heatmap/tip-heatmap.component';
import {
  HEATMAP_LAYERS,
  HeatmapLayer,
  storeHeatmapLayer,
  storedHeatmapLayer,
} from '../../../game/models/heatmap-layer';
import { HeatmapCell, HitPatternDto } from '../../dto/hit-pattern.dto';
import { Comparison } from '../../models/comparison';

/** Where a player's darts landed, as a tip cloud or by field, beside a compared player's if
 * there is one; projected content goes below. */
@Component({
  selector: 'app-hit-pattern',
  imports: [FieldHeatmapComponent, FormsModule, NgTemplateOutlet, SelectButton, TipHeatmapComponent],
  templateUrl: './hit-pattern.component.html',
  styleUrl: './hit-pattern.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HitPatternComponent {
  /** Darts per called-out label, and the located ones the cloud draws. */
  readonly fields = input.required<Readonly<Record<string, number>>>();
  readonly locatedFields = input.required<Readonly<Record<string, number>>>();
  readonly heatmap = input.required<readonly HeatmapCell[]>();
  readonly comparison = input<Comparison<HitPatternDto> | null>(null);

  protected readonly layerOptions = [...HEATMAP_LAYERS];
  protected readonly layer = signal(storedHeatmapLayer());
  protected readonly pinnedField = signal<string | null>(null);

  protected readonly fieldCounts = computed(() => new Map(Object.entries(this.fields())));
  protected readonly tipCounts = computed(() => new Map(Object.entries(this.locatedFields())));
  protected readonly otherFieldCounts = computed(
    () => new Map(Object.entries(this.comparison()?.statistics.fields ?? {})),
  );
  protected readonly otherTipCounts = computed(
    () => new Map(Object.entries(this.comparison()?.statistics.locatedFields ?? {})),
  );

  protected selectLayer(layer: HeatmapLayer): void {
    this.layer.set(layer);
    storeHeatmapLayer(layer);
  }
}
