import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { PlayerStatisticsDto } from '../../dto/player-statistics.dto';
import { StatisticsService } from '../../services/statistics.service';
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
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';

@Component({
  selector: 'app-statistics',
  imports: [
    BackLinkComponent,
    DecimalPipe,
    LoadingStateComponent,
    EmptyStateComponent,
    FieldHeatmapComponent,
    LoadErrorComponent,
    FormsModule,
    SelectButton,
    TipHeatmapComponent,
  ],
  templateUrl: './statistics.component.html',
  styleUrl: './statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatisticsComponent {
  private readonly statistics = inject(StatisticsService);

  protected readonly totals = signal<PlayerStatisticsDto | null>(null);
  protected readonly loading = signal(true);
  protected readonly failed = signal(false);

  protected readonly layerOptions = [...HEATMAP_LAYERS];
  protected readonly layer = signal(storedHeatmapLayer());

  protected readonly fieldCounts = computed(
    () => new Map(Object.entries(this.totals()?.fields ?? {})),
  );

  /** Darts that finished a leg, out of darts thrown while one dart could finish. */
  protected readonly checkoutRate = computed(() => {
    const totals = this.totals();
    return !totals || totals.checkoutAttempts === 0
      ? null
      : totals.checkoutHits / totals.checkoutAttempts;
  });

  /** Legs won out of legs that reached a finishable score at least once. */
  protected readonly legRate = computed(() => {
    const totals = this.totals();
    return !totals || totals.legsWithChance === 0 ? null : totals.legsWon / totals.legsWithChance;
  });

  constructor() {
    void this.load();
  }

  protected selectLayer(layer: HeatmapLayer): void {
    this.layer.set(layer);
    storeHeatmapLayer(layer);
  }

  protected async load(): Promise<void> {
    this.loading.set(true);
    this.failed.set(false);
    try {
      this.totals.set(await this.statistics.load());
    } catch {
      this.failed.set(true);
    } finally {
      this.loading.set(false);
    }
  }
}
