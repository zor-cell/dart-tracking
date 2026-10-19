import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { ProgressSpinner } from 'primeng/progressspinner';
import { GameDetailDto } from '../../dto/game-detail.dto';
import { GAME_STATUS_LABELS } from '../../models/game-filter';
import { CHECKOUT_MODES } from '../../models/checkout-mode';
import { GameHistoryService } from '../../services/game-history.service';
import { GameReplayComponent } from '../game-replay/game-replay.component';

@Component({
  selector: 'app-game-detail',
  imports: [
    Button,
    DatePipe,
    DecimalPipe,
    GameReplayComponent,
    ProgressSpinner,
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
  protected readonly statusLabels = GAME_STATUS_LABELS;

  protected readonly isElimination = computed(() => this.detail()?.game.variant === 'elimination');

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
    void this.load(this.route.snapshot.paramMap.get('gameId') ?? '');
  }

  protected rate(hits: number, attempts: number): number | null {
    return attempts === 0 ? null : hits / attempts;
  }

  private async load(gameId: string): Promise<void> {
    try {
      this.detail.set(await this.history.detail(gameId));
    } catch {
      this.missing.set(true);
    } finally {
      this.loading.set(false);
    }
  }
}
