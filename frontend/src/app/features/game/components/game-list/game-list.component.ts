import { DatePipe, formatDate } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  LOCALE_ID,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { DatePicker } from 'primeng/datepicker';
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
  PLAYER_COUNTS,
  PlayerCount,
} from '../../models/game-filter';
import { GAME_MODES, GameMode } from '../../models/game-mode';
import { GAME_VARIANTS, GameVariant } from '../../models/game-variant';
import { GameHistoryService } from '../../services/game-history.service';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { ListToolbarComponent } from '../../../../core/view/components/list-toolbar/list-toolbar.component';
import { FilterChip } from '../../../../core/view/models/filter-chip';
import { PagedTable } from '../../../../core/view/models/paged-table';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';

@Component({
  selector: 'app-game-list',
  imports: [
    BackLinkComponent,
    DatePicker,
    DatePipe,
    EmptyStateComponent,
    ListToolbarComponent,
    LoadErrorComponent,
    LoadingStateComponent,
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
  private readonly locale = inject(LOCALE_ID);

  protected readonly variantOptions = [...GAME_VARIANTS];
  protected readonly modeOptions = GAME_MODES.map((mode) => ({ label: `${mode}`, value: mode }));
  protected readonly statusOptions = Object.entries(GAME_STATUS_LABELS).map(([value, label]) => ({
    label,
    value: value as GameStatus,
  }));
  protected readonly playerCountOptions = Object.entries(PLAYER_COUNTS).map(([value, count]) => ({
    label: count.label,
    value: value as PlayerCount,
  }));
  protected readonly opponents = signal<PlayerIdentityDto[]>([]);

  protected readonly filters = this.fb.group({
    variant: this.fb.control<GameVariant | null>(null),
    mode: this.fb.control<GameMode | null>(null),
    status: this.fb.control<GameStatus | null>(null),
    opponentId: this.fb.control<string | null>(null),
    players: this.fb.control<PlayerCount | null>(null),
    period: this.fb.control<(Date | null)[] | null>(null),
  });

  protected readonly games = new PagedTable<GameSummaryDto>((limit, offset) =>
    this.history.list(limit, offset, this.criteria()),
  );

  private readonly filterValue = toSignal(this.filters.valueChanges, {
    initialValue: this.filters.value,
  });
  /** The filters in use, as chips above the table. */
  protected readonly chips = computed<FilterChip[]>(() => {
    const { variant, mode, status, opponentId, players, period } = this.filterValue();
    const chips: FilterChip[] = [];
    if (variant) {
      const label = GAME_VARIANTS.find((option) => option.value === variant)?.label ?? variant;
      chips.push({ key: 'variant', label });
    }
    if (mode) {
      chips.push({ key: 'mode', label: `${mode}` });
    }
    if (status) {
      chips.push({ key: 'status', label: GAME_STATUS_LABELS[status] });
    }
    if (opponentId) {
      const name = this.opponents().find((player) => player.id === opponentId)?.name;
      chips.push({ key: 'opponentId', label: `Mit ${name ?? 'Mitspieler'}` });
    }
    if (players) {
      chips.push({ key: 'players', label: PLAYER_COUNTS[players].label });
    }
    const [start, end] = period ?? [];
    if (start) {
      const day = (date: Date) => formatDate(date, 'dd.MM.yy', this.locale);
      const label = end && end.getTime() !== start.getTime() ? `${day(start)} – ${day(end)}` : day(start);
      chips.push({ key: 'period', label });
    }
    return chips;
  });

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

  protected clearFilter(key: string): void {
    this.filters.get(key)?.reset();
  }

  /** The form as a filter; a range with one day picked covers that day. */
  private criteria(): GameFilter {
    const { variant, mode, status, opponentId, players, period } = this.filters.getRawValue();
    const [start, end] = period ?? [];
    const count = players ? PLAYER_COUNTS[players] : null;
    return {
      variant,
      mode,
      status,
      opponentId,
      minPlayers: count?.min ?? null,
      maxPlayers: count?.max ?? null,
      since: start ?? null,
      until: start ? nextDay(end ?? start) : null,
    };
  }
}

function nextDay(day: Date): Date {
  return new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1);
}
