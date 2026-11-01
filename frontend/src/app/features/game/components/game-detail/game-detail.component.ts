import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { Message } from 'primeng/message';
import { Tag } from 'primeng/tag';
import { TableModule } from 'primeng/table';
import { GameDetailDto } from '../../dto/game-detail.dto';
import { GAME_STATUS_LABELS, GAME_STATUS_SEVERITIES, isResumable } from '../../models/game-filter';
import { CHECKOUT_MODES } from '../../models/checkout-mode';
import { GAME_VARIANTS } from '../../models/game-variant';
import { activeGameId } from '../../services/active-game';
import { GameHistoryService } from '../../services/game-history.service';
import { GameReplayComponent } from '../game-replay/game-replay.component';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { ConfirmService } from '../../../../core/view/services/confirm.service';

const GAME_FIGURES = ['average', 'firstNine', 'darts', 'bestVisit', 'grouping'] as const;
const CHECKOUT_FIGURES = ['checkout', 'doubleDistance', 'busts'] as const;

type Figure = (typeof GAME_FIGURES)[number] | (typeof CHECKOUT_FIGURES)[number];

/** One row of the figures table and the subheading it sits under. */
interface FigureRow {
  readonly figure: Figure;
  readonly group: string;
}

function sum(values: readonly number[]): number {
  return values.reduce((total, value) => total + value, 0);
}

/** A visit index from the query params; null for none or one that is no index. */
function visitParam(raw: string | null): number | null {
  const visit = raw === null ? NaN : Number(raw);
  return Number.isInteger(visit) && visit >= 0 ? visit : null;
}

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
    Message,
    RouterLink,
    TableModule,
    Tag,
  ],
  templateUrl: './game-detail.component.html',
  styleUrl: './game-detail.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameDetailComponent {
  private readonly history = inject(GameHistoryService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly confirm = inject(ConfirmService);

  protected readonly detail = signal<GameDetailDto | null>(null);
  protected readonly loading = signal(true);
  protected readonly missing = signal(false);
  protected readonly failed = signal(false);
  protected readonly statusLabels = GAME_STATUS_LABELS;
  protected readonly statusSeverities = GAME_STATUS_SEVERITIES;
  /** The visit a link asked to open the replay on. */
  protected readonly startVisit = visitParam(this.route.snapshot.queryParamMap.get('visit'));

  protected readonly resumable = computed(() => {
    const detail = this.detail();
    return detail !== null && isResumable(detail.status);
  });
  protected readonly resuming = signal(false);
  protected readonly hidden = computed(() => this.detail()?.status === 'discarded');
  protected readonly hiding = signal(false);
  /** What went wrong with the last resume or show/hide, under the heading. */
  protected readonly actionError = signal<string | null>(null);

  protected readonly isElimination = computed(() => this.detail()?.game.variant === 'elimination');

  protected readonly variantLabel = computed(() => {
    const variant = this.detail()?.game.variant;
    return GAME_VARIANTS.find((option) => option.value === variant)?.label ?? '';
  });

  protected readonly checkoutLabel = computed(() => {
    const mode = this.detail()?.game.checkoutMode;
    return CHECKOUT_MODES.find((option) => option.value === mode)?.label ?? '';
  });

  /** Minutes of actual play, while that is known. */
  protected readonly durationMinutes = computed(() => {
    const seconds = this.detail()?.playedSeconds;
    return seconds === null || seconds === undefined ? null : Math.max(1, Math.round(seconds / 60));
  });

  /** Players with their figures, in the order they threw. */
  protected readonly standings = computed(() => {
    const detail = this.detail();
    if (!detail) {
      return [];
    }
    const { game, statistics, visits } = detail;
    return game.players.map((player, seat) => ({
      ...player,
      won: player.id === game.winnerId,
      statistics: statistics[seat],
      busts: visits.filter((visit) => visit.playerId === player.id && visit.busted).length,
      doublesLocated: sum(statistics[seat].doubles.map((double) => double.located)),
      doublesThrown: sum(statistics[seat].doubles.map((double) => double.attempts)),
    }));
  });

  constructor() {
    void this.load();
  }

  /** The figures compared per player, grouped; elimination has no checkout, so busts join the game. */
  protected readonly figureRows = computed<FigureRow[]>(() => {
    const game = GAME_FIGURES.map((figure) => ({ figure, group: 'Spiel' }));
    return this.isElimination()
      ? [...game, { figure: 'busts', group: 'Spiel' }]
      : [...game, ...CHECKOUT_FIGURES.map((figure) => ({ figure, group: 'Checkout' }))];
  });

  protected confirmResume(): void {
    this.confirm.ask(
      'Spiel fortsetzen?',
      'Das Spiel läuft danach wieder und zählt erst in die Statistik, wenn es beendet ist.',
      'Fortsetzen',
      () => void this.resume(),
      true,
    );
  }

  /** Takes the game up again and goes into it; a device that still has it open skips the role. */
  private async resume(): Promise<void> {
    const gameId = this.detail()?.game.id;
    if (!gameId) {
      return;
    }
    this.resuming.set(true);
    this.actionError.set(null);
    try {
      await this.history.resume(gameId);
      await this.router.navigate(activeGameId() === gameId ? ['/game'] : ['/game/join', gameId]);
    } catch (failure) {
      this.actionError.set(
        httpErrorMessage(
          failure,
          { 404: 'Dieses Spiel ist schon vorbei und lässt sich nicht fortsetzen.' },
          'Das Spiel konnte nicht fortgesetzt werden.',
        ),
      );
    } finally {
      this.resuming.set(false);
    }
  }

  protected confirmToggleHidden(): void {
    if (this.hidden()) {
      this.confirm.ask(
        'Wieder einblenden?',
        'Das Spiel steht wieder in deiner Spieleliste und zählt in deine Statistik, sobald es ' +
          'beendet ist.',
        'Einblenden',
        () => void this.toggleHidden(),
        true,
      );
    } else {
      this.confirm.ask(
        'Für dich ausblenden?',
        'Das Spiel zählt nicht mehr in deine Statistik und verschwindet aus deiner Spieleliste, ' +
          'bis du nach „ausgeblendet“ filterst. Für die anderen Spieler ändert sich nichts. Du ' +
          'kannst es hier jederzeit wieder einblenden.',
        'Ausblenden',
        () => void this.toggleHidden(),
        true,
      );
    }
  }

  /** Hides the game for this account or shows it again, then reads its new status. */
  private async toggleHidden(): Promise<void> {
    const gameId = this.detail()?.game.id;
    if (!gameId) {
      return;
    }
    this.hiding.set(true);
    this.actionError.set(null);
    try {
      await this.history.setCounted(gameId, this.hidden());
      this.detail.set(await this.history.detail(gameId));
    } catch (failure) {
      this.actionError.set(
        httpErrorMessage(failure, {}, 'Das Spiel konnte nicht geändert werden.'),
      );
    } finally {
      this.hiding.set(false);
    }
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
