import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Button } from 'primeng/button';
import { DatePicker } from 'primeng/datepicker';
import { Popover } from 'primeng/popover';
import { Select } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { Tag } from 'primeng/tag';
import { PlayerIdentityDto } from '../../../player/dto/player-identity.dto';
import { PlayerService } from '../../../player/services/player.service';
import { GameStatus, GameSummaryDto } from '../../dto/game-summary.dto';
import {
  GAME_STATUS_LABELS,
  GAME_STATUS_SEVERITIES,
  GameFilter,
  GameStatusSeverity,
} from '../../models/game-filter';
import { GAME_MODES, GameMode } from '../../models/game-mode';
import { GAME_VARIANTS, GameVariant } from '../../models/game-variant';
import { GameHistoryService } from '../../services/game-history.service';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { PagedTable } from '../../../../core/view/models/paged-table';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';

@Component({
  selector: 'app-game-list',
  imports: [
    BackLinkComponent,
    Button,
    DatePicker,
    DatePipe,
    EmptyStateComponent,
    LoadErrorComponent,
    LoadingStateComponent,
    Popover,
    ReactiveFormsModule,
    Select,
    TableModule,
    Tag,
  ],
  templateUrl: './game-list.component.html',
  styleUrl: './game-list.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameListComponent {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly history = inject(GameHistoryService);
  private readonly players = inject(PlayerService);

  protected readonly variantOptions = [...GAME_VARIANTS];
  protected readonly modeOptions = GAME_MODES.map((mode) => ({ label: `${mode}`, value: mode }));
  protected readonly statusOptions = Object.entries(GAME_STATUS_LABELS).map(([value, label]) => ({
    label,
    value: value as GameStatus,
  }));
  protected readonly opponents = signal<PlayerIdentityDto[]>([]);

  protected readonly filters = this.fb.group({
    variant: this.fb.control<GameVariant | null>(null),
    mode: this.fb.control<GameMode | null>(null),
    status: this.fb.control<GameStatus | null>(null),
    opponentId: this.fb.control<string | null>(null),
    period: this.fb.control<(Date | null)[] | null>(null),
  });

  protected readonly games = new PagedTable<GameSummaryDto>((limit, offset) =>
    this.history.list(limit, offset, this.criteria()),
  );

  private readonly filterValue = toSignal(this.filters.valueChanges, {
    initialValue: this.filters.value,
  });
  protected readonly activeFilters = computed(
    () => Object.values(this.filterValue()).filter((value) => value !== null).length,
  );

  constructor() {
    void this.games.load();
    void this.players.list().then((all) => this.opponents.set(all.filter((p) => !p.isSelf)));
    this.filters.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => this.games.restart());
  }

  protected open(game: GameSummaryDto): void {
    void this.router.navigate(['/account/games', game.id]);
  }

  protected statusLabel(game: GameSummaryDto): string {
    return GAME_STATUS_LABELS[game.status];
  }

  protected statusSeverity(game: GameSummaryDto): GameStatusSeverity {
    return GAME_STATUS_SEVERITIES[game.status];
  }

  protected resetFilters(): void {
    this.filters.reset();
  }

  /** The form as a filter; a range with one day picked covers that day. */
  private criteria(): GameFilter {
    const { variant, mode, status, opponentId, period } = this.filters.getRawValue();
    const [start, end] = period ?? [];
    return {
      variant,
      mode,
      status,
      opponentId,
      since: start ?? null,
      until: start ? nextDay(end ?? start) : null,
    };
  }
}

function nextDay(day: Date): Date {
  return new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1);
}
