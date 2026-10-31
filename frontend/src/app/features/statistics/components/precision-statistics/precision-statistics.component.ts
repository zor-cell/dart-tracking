import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SelectButton } from 'primeng/selectbutton';
import { DistanceScaleComponent } from '../../../game/components/distance-scale/distance-scale.component';
import { FieldHeatmapComponent } from '../../../game/components/field-heatmap/field-heatmap.component';
import { TipHeatmapComponent } from '../../../game/components/tip-heatmap/tip-heatmap.component';
import { dartColor } from '../../../game/models/dart-colors';
import {
  HEATMAP_LAYERS,
  HeatmapLayer,
  storeHeatmapLayer,
  storedHeatmapLayer,
} from '../../../game/models/heatmap-layer';
import { PlayerStatisticsDto } from '../../dto/player-statistics.dto';

/** The general figures, the hit picture and how the darts group: spread, each dart's place. */
@Component({
  selector: 'app-precision-statistics',
  imports: [
    DecimalPipe,
    DistanceScaleComponent,
    FieldHeatmapComponent,
    FormsModule,
    SelectButton,
    TipHeatmapComponent,
  ],
  templateUrl: './precision-statistics.component.html',
  styleUrl: './precision-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PrecisionStatisticsComponent {
  readonly statistics = input.required<PlayerStatisticsDto>();

  protected readonly layerOptions = [...HEATMAP_LAYERS];
  protected readonly layer = signal(storedHeatmapLayer());
  /** The field picked on the heatmap, kept when the layer changes. */
  protected readonly pinnedField = signal<string | null>(null);

  /** Legs won out of every leg played. */
  protected readonly wonRate = computed(() => {
    const { legsWon, legs } = this.statistics();
    return legs === 0 ? null : legsWon / legs;
  });

  protected readonly fieldCounts = computed(
    () => new Map(Object.entries(this.statistics().fields)),
  );
  protected readonly tipCounts = computed(
    () => new Map(Object.entries(this.statistics().locatedFields)),
  );

  /** The wider axis against the narrower one, and the ellipse drawn from them. */
  protected readonly spread = computed(() => {
    const scatter = this.statistics().scatter;
    if (scatter === null) {
      return null;
    }
    return {
      ratio: scatter.major / Math.max(scatter.minor, 0.1),
      ry: scatter.minor / Math.max(scatter.major, 0.1),
      rotation: -scatter.angle,
    };
  });

  /** Each dart's points per throw, with its share of the best of the three for the bar. */
  protected readonly darts = computed(() => {
    const averages = this.statistics().dartAverages;
    const best = Math.max(1, ...averages.map((average) => average ?? 0));
    return averages.map((average, place) => ({
      place: place + 1,
      average,
      color: dartColor(place),
      share: ((average ?? 0) / best) * 100,
    }));
  });

  protected selectLayer(layer: HeatmapLayer): void {
    this.layer.set(layer);
    storeHeatmapLayer(layer);
  }
}
