import { DecimalPipe } from '@angular/common';
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
import { PlayerStatisticsDto } from '../../dto/player-statistics.dto';

/** Below this ratio of the axes the spread counts as even. */
const ROUND_RATIO = 1.2;

/** The general figures, the hit picture and how the darts group: spread, each dart's place. */
@Component({
  selector: 'app-precision-statistics',
  imports: [DecimalPipe, FieldHeatmapComponent, FormsModule, SelectButton, TipHeatmapComponent],
  templateUrl: './precision-statistics.component.html',
  styleUrl: './precision-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PrecisionStatisticsComponent {
  readonly statistics = input.required<PlayerStatisticsDto>();

  protected readonly layerOptions = [...HEATMAP_LAYERS];
  protected readonly layer = signal(storedHeatmapLayer());

  protected readonly fieldCounts = computed(
    () => new Map(Object.entries(this.statistics().fields)),
  );

  /** The wider axis against the narrower one, and which way the wider one runs. */
  protected readonly spread = computed(() => {
    const scatter = this.statistics().scatter;
    if (scatter === null) {
      return null;
    }
    const ratio = scatter.major / Math.max(scatter.minor, 0.1);
    const tilt = Math.abs(scatter.angle);
    const direction =
      ratio < ROUND_RATIO
        ? 'gleichmäßig nach allen Seiten'
        : tilt > 60
          ? 'nach oben und unten stärker'
          : tilt < 30
            ? 'zur Seite stärker'
            : 'schräg stärker';
    return {
      ratio,
      direction,
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
      share: ((average ?? 0) / best) * 100,
    }));
  });

  protected selectLayer(layer: HeatmapLayer): void {
    this.layer.set(layer);
    storeHeatmapLayer(layer);
  }
}
