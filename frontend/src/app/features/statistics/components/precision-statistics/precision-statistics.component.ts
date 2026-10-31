import { DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Params, RouterLink } from '@angular/router';
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
import { backState } from '../../../../core/view/models/back-state';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { PlayerStatisticsDto } from '../../dto/player-statistics.dto';
import { ScatterDto } from '../../dto/scatter.dto';
import { COMPARE_COLOR, Comparison, OWN_COLOR } from '../../models/comparison';
import { visitTotal } from '../../models/visit-scores';
import { StatDeltaComponent } from '../stat-delta/stat-delta.component';
import { StatSketchComponent } from '../stat-sketch/stat-sketch.component';

/** The general figures, the hit picture and how the darts group: spread, each dart's place. */
@Component({
  selector: 'app-precision-statistics',
  imports: [
    DecimalPipe,
    DistanceScaleComponent,
    FieldHeatmapComponent,
    FormsModule,
    InfoHintComponent,
    NgTemplateOutlet,
    RouterLink,
    SelectButton,
    StatDeltaComponent,
    StatSketchComponent,
    TipHeatmapComponent,
  ],
  templateUrl: './precision-statistics.component.html',
  styleUrl: './precision-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PrecisionStatisticsComponent {
  readonly statistics = input.required<PlayerStatisticsDto>();
  /** Another player's figures set beside one's own; the hit picture is left out meanwhile. */
  readonly comparison = input<Comparison | null>(null);
  protected readonly ownColor = OWN_COLOR;
  protected readonly compareColor = COMPARE_COLOR;
  protected readonly pairColors = [OWN_COLOR, COMPARE_COLOR] as const;
  /** Brings the views the cards open back here. */
  protected readonly returnState = backState('Statistik');
  /** The page's filters as the game list reads them, carried into its links. */
  readonly listParams = input<Params>({});

  protected readonly layerOptions = [...HEATMAP_LAYERS];
  protected readonly layer = signal(storedHeatmapLayer());
  /** The field picked on the heatmap, kept when the layer changes. */
  protected readonly pinnedField = signal<string | null>(null);

  /** Legs won out of every leg played, in percent. */
  protected readonly wonRate = computed(() => wonRate(this.statistics()));
  protected readonly otherWonRate = computed(() => {
    const other = this.comparison()?.statistics;
    return other ? wonRate(other) : null;
  });

  /** Visits reaching each band, also as a share of all visits in percent beside another's. */
  protected readonly bands = computed(() => {
    const own = this.statistics();
    const other = this.comparison()?.statistics ?? null;
    const share = (statistics: PlayerStatisticsDto, count: number) => {
      const total = visitTotal(statistics.visitScores);
      return total === 0 ? null : (count / total) * 100;
    };
    const figure = (counts: (statistics: PlayerStatisticsDto) => number) => ({
      count: counts(own),
      share: share(own, counts(own)),
      otherShare: other ? share(other, counts(other)) : null,
    });
    return {
      180: figure((statistics) => statistics.visits180),
      140: figure((statistics) => statistics.visits140Plus),
      100: figure((statistics) => statistics.visits100Plus),
      60: figure((statistics) => statistics.visits60Plus),
    } as Record<number, { count: number; share: number | null; otherShare: number | null }>;
  });

  /** Darts per field, all of them or only the located ones the cloud draws, as the heatmaps
   * take them; the compared player's too, null without one. */
  protected readonly fieldCounts = computed(() => fieldCounts(this.statistics()));
  protected readonly tipCounts = computed(() => tipCounts(this.statistics()));
  protected readonly otherFieldCounts = computed(() => {
    const other = this.comparison()?.statistics;
    return other ? fieldCounts(other) : null;
  });
  protected readonly otherTipCounts = computed(() => {
    const other = this.comparison()?.statistics;
    return other ? tipCounts(other) : null;
  });

  protected readonly spread = computed(() => spreadOf(this.statistics().scatter));
  protected readonly otherSpread = computed(() =>
    spreadOf(this.comparison()?.statistics.scatter ?? null),
  );

  /** Each dart's points per throw, with its share of the best one shown for the bar; beside
   * another player one's own bars take the comparison's blue instead of the dart colours. */
  protected readonly darts = computed(() => {
    const averages = this.statistics().dartAverages;
    const compared = this.comparison() !== null;
    const others = this.comparison()?.statistics.dartAverages ?? [];
    const best = Math.max(1, ...[...averages, ...others].map((average) => average ?? 0));
    return averages.map((average, place) => {
      const other = others[place] ?? null;
      return {
        place: place + 1,
        average,
        other,
        color: compared ? OWN_COLOR : dartColor(place),
        share: ((average ?? 0) / best) * 100,
        otherShare: ((other ?? 0) / best) * 100,
      };
    });
  });

  protected selectLayer(layer: HeatmapLayer): void {
    this.layer.set(layer);
    storeHeatmapLayer(layer);
  }

  /** The game list narrowed to games with a visit in `band`, under the page's filters. */
  protected bandParams(band: number): Params {
    return { ...this.listParams(), visit: band };
  }
}

function fieldCounts({ fields }: PlayerStatisticsDto): ReadonlyMap<string, number> {
  return new Map(Object.entries(fields));
}

function tipCounts({ locatedFields }: PlayerStatisticsDto): ReadonlyMap<string, number> {
  return new Map(Object.entries(locatedFields));
}

function wonRate({ legsWon, legs }: PlayerStatisticsDto): number | null {
  return legs === 0 ? null : (legsWon / legs) * 100;
}

/** The wider axis against the narrower one, and the ellipse drawn from them. */
function spreadOf(scatter: ScatterDto | null) {
  if (scatter === null) {
    return null;
  }
  return {
    ratio: scatter.major / Math.max(scatter.minor, 0.1),
    ry: scatter.minor / Math.max(scatter.major, 0.1),
    rotation: -scatter.angle,
  };
}
