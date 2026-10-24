import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { GameDetailDto } from '../../dto/game-detail.dto';
import { GAME_STATUS_LABELS } from '../../models/game-filter';
import { CHECKOUT_MODES } from '../../models/checkout-mode';
import { GAME_VARIANTS } from '../../models/game-variant';
import { GameHistoryService } from '../../services/game-history.service';
import { GameReplayComponent } from '../game-replay/game-replay.component';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';

@Component({
  selector: 'app-game-detail',
  imports: [
    BackLinkComponent,
    Button,
    DatePipe,
    DecimalPipe,
    GameReplayComponent,
    LoadingStateComponent,
    EmptyStateComponent,
    LoadErrorComponent,
    RouterLink,
  ],
  templateUrl: './game-detail.component.html',
  styleUrl: './game-detail.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameDetailComponent {
  private readonly history = inject(GameHistoryService);
  private readonly route = inject(ActivatedRoute);

  protected readonly detail = signal<GameDetailDto | null>(null);
  protected readonly loading = signal(true);
  protected readonly missing = signal(false);
  protected readonly failed = signal(false);
  protected readonly statusLabels = GAME_STATUS_LABELS;

  protected readonly isElimination = computed(() => this.detail()?.game.variant === 'elimination');

  protected readonly variantLabel = computed(() => {
    const variant = this.detail()?.game.variant;
    return GAME_VARIANTS.find((option) => option.value === variant)?.label ?? '';
  });

  protected readonly checkoutLabel = computed(() => {
    const mode = this.detail()?.game.checkoutMode;
    return CHECKOUT_MODES.find((option) => option.value === mode)?.label ?? '';
  });

  /** Minutes from the first to the last recorded moment, while that is known. */
  protected readonly durationMinutes = computed(() => {
    const detail = this.detail();
    if (!detail?.finishedAt) {
      return null;
    }
    const millis = Date.parse(detail.finishedAt) - Date.parse(detail.createdAt);
    return Math.max(1, Math.round(millis / 60_000));
  });

  /** Players with their figures, the winner first, then by points still needed. */
  protected readonly standings = computed(() => {
    const detail = this.detail();
    if (!detail) {
      return [];
    }
    const { game, statistics, visits } = detail;
    return game.players
      .map((player, seat) => ({
        ...player,
        won: player.id === game.winnerId,
        statistics: statistics[seat],
        busts: visits.filter((visit) => visit.playerId === player.id && visit.busted).length,
      }))
      .sort((a, b) => Number(b.won) - Number(a.won) || a.remaining - b.remaining);
  });

  constructor() {
    void this.load();
  }

  protected rate(hits: number, attempts: number): number | null {
    return attempts === 0 ? null : hits / attempts;
  }

  protected async load(): Promise<void> {
    const gameId = this.route.snapshot.paramMap.get('gameId') ?? '';
    this.loading.set(true);
    this.failed.set(false);
    try {
      this.detail.set(await this.history.detail(gameId));
    } catch (failure) {
      if (failure instanceof HttpErrorResponse && failure.status === 404) {
        this.missing.set(true);
      } else {
        this.failed.set(true);
      }
    } finally {
      this.loading.set(false);
    }
  }
}
