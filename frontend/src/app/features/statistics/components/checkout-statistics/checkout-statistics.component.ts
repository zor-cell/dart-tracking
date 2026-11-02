import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  input,
  signal,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { SelectButton } from 'primeng/selectbutton';
import { DistanceScaleComponent } from '../../../game/components/distance-scale/distance-scale.component';
import {
  HEATMAP_LAYERS,
  HeatmapLayer,
  storeHeatmapLayer,
  storedHeatmapLayer,
} from '../../../game/models/heatmap-layer';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { backState } from '../../../../core/view/models/back-state';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { PlayerStatisticsDto } from '../../dto/player-statistics.dto';
import { COMPARE_COLOR, Comparison, OWN_COLOR } from '../../models/comparison';
import { DoubleBoardComponent } from '../double-board/double-board.component';
import { ComparedValueComponent } from '../compared-value/compared-value.component';
import { DeltaMarkComponent } from '../delta-mark/delta-mark.component';
import { StatSketchComponent } from '../stat-sketch/stat-sketch.component';

/** Checkout figures: the rates, how far off the doubles went and each double on the board. */
@Component({
  selector: 'app-checkout-statistics',
  imports: [
    ComparedValueComponent,
    DeltaMarkComponent,
    DecimalPipe,
    DistanceScaleComponent,
    DoubleBoardComponent,
    EmptyStateComponent,
    FormsModule,
    InfoHintComponent,
    RouterLink,
    SelectButton,
    StatSketchComponent,
  ],
  templateUrl: './checkout-statistics.component.html',
  styleUrl: './checkout-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CheckoutStatisticsComponent {
  readonly statistics = input.required<PlayerStatisticsDto>();
  /** Another player's figures set beside one's own; the doubles board is left out meanwhile. */
  readonly comparison = input<Comparison | null>(null);
  protected readonly pairColors = [OWN_COLOR, COMPARE_COLOR] as const;
  /** Brings the views the cards open back here. */
  protected readonly returnState = backState($localize`:@@auth.account.stats:Statistik`);

  protected readonly selected = signal<string | null>(null);
  protected readonly layerOptions = [...HEATMAP_LAYERS];
  /** Tips or fields, the same on both boards of a comparison. */
  protected readonly layer = signal<HeatmapLayer>(storedHeatmapLayer());

  protected readonly checkoutRate = computed(() => checkoutRate(this.statistics()));
  protected readonly otherCheckoutRate = computed(() => {
    const other = this.comparison()?.statistics;
    return other ? checkoutRate(other) : null;
  });

  constructor() {
    // New figures drop a pick that is no longer among their doubles.
    effect(() => {
      const doubles = this.statistics().doubles;
      untracked(() => {
        if (!doubles.some((double) => double.label === this.selected())) {
          this.selected.set(null);
        }
      });
    });
  }

  protected selectLayer(layer: HeatmapLayer): void {
    this.layer.set(layer);
    storeHeatmapLayer(layer);
  }
}

/** Darts that finished a leg, out of darts thrown while one dart could finish, in percent. */
function checkoutRate({ checkoutHits, checkoutAttempts }: PlayerStatisticsDto): number | null {
  return checkoutAttempts === 0 ? null : (checkoutHits / checkoutAttempts) * 100;
}
