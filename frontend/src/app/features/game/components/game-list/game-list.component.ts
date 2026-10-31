import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
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
  VISIT_BANDS,
  VisitBand,
  visitBandLabel,
} from '../../models/game-filter';
import { GAME_MODES, GameMode } from '../../models/game-mode';
import { GAME_VARIANTS, GameVariant } from '../../models/game-variant';
import { GameHistoryService } from '../../services/game-history.service';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { ListToolbarComponent } from '../../../../core/view/components/list-toolbar/list-toolbar.component';
import { dayRangeBounds, dayRangeLabel } from '../../../../core/view/models/day-range';
import { FilterChip, FilterSuggestion } from '../../../../core/view/models/filter-chip';
import { PagedTable } from '../../../../core/view/models/paged-table';
import {
  DAY_RANGE_PARAM,
  QueryState,
  TEXT_PARAM,
  oneOfParam,
} from '../../../../core/view/models/query-state';
import { FilterMemoryService } from '../../../../core/view/services/filter-memory.service';

/** The filters whose picks are remembered and offered back; the period is not among them. */
const REMEMBERED = ['variant', 'mode', 'status', 'opponentId', 'players'] as const;

/** How each filter is kept in the query params. */
const FILTER_PARAMS = {
  variant: oneOfParam(GAME_VARIANTS.map((variant) => variant.value)),
  mode: oneOfParam(GAME_MODES),
  status: oneOfParam(Object.keys(GAME_STATUS_LABELS) as GameStatus[]),
  opponentId: TEXT_PARAM,
  players: oneOfParam(Object.keys(PLAYER_COUNTS) as PlayerCount[]),
  period: DAY_RANGE_PARAM,
  visit: oneOfParam(VISIT_BANDS),
};

/** Offered while the account has no picks of its own. */
const DEFAULT_SUGGESTIONS: FilterSuggestion[] = [
  { key: 'status', label: GAME_STATUS_LABELS.finished, value: 'finished' },
  { key: 'players', label: PLAYER_COUNTS.duel.label, value: 'duel' },
];
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
  private readonly memory = inject(FilterMemoryService);
  private readonly destroyRef = inject(DestroyRef);

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
  protected readonly visitOptions = VISIT_BANDS.map((band) => ({
    label: visitBandLabel(band),
    value: band,
  }));
  protected readonly opponents = signal<PlayerIdentityDto[]>([]);
  protected readonly query = signal('');

  protected readonly filters = this.fb.group({
    variant: this.fb.control<GameVariant | null>(null),
    mode: this.fb.control<GameMode | null>(null),
    status: this.fb.control<GameStatus | null>(null),
    opponentId: this.fb.control<string | null>(null),
    players: this.fb.control<PlayerCount | null>(null),
    period: this.fb.control<(Date | null)[] | null>(null),
    visit: this.fb.control<VisitBand | null>(null),
  });
  private readonly queryState = new QueryState();

  protected readonly games = new PagedTable<GameSummaryDto>((limit, offset) =>
    this.history.list(limit, offset, this.criteria()),
  );

  private readonly filterValue = toSignal(this.filters.valueChanges, {
    initialValue: this.filters.value,
  });
  /** The filters in use, as chips above the table. */
  protected readonly chips = computed<FilterChip[]>(() => {
    const value = this.filterValue();
    const chips: FilterChip[] = REMEMBERED.flatMap((key) => {
      const picked = value[key];
      return picked ? [{ key, label: this.labelOf(key, picked) ?? 'Mit Mitspieler' }] : [];
    });
    const label = dayRangeLabel(value.period ?? null, this.locale);
    if (label) {
      chips.push({ key: 'period', label });
    }
    if (value.visit) {
      chips.push({ key: 'visit', label: `Mit ${visitBandLabel(value.visit)}` });
    }
    return chips;
  });
  /** Common filters one tap away, for those still open. */
  protected readonly suggestions = computed<FilterSuggestion[]>(() => {
    const value = this.filterValue() as Record<string, unknown>;
    return this.memory.suggest(
      'games',
      DEFAULT_SUGGESTIONS,
      (key, picked) => this.labelOf(key, picked),
      (key) => !value[key],
    );
  });
  /** Whether the search or a filter narrows the list. */
  protected readonly filtered = computed(() => this.query() !== '' || this.chips().length > 0);

  constructor() {
    this.queryState.form(this.filters, FILTER_PARAMS);
    void this.games.load();
    void this.players.list().then((all) => this.opponents.set(all.filter((p) => !p.isSelf)));
    void this.memory.load();
    this.memory.watch('games', this.filters, REMEMBERED, this.destroyRef);
    this.filters.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => this.games.restart());
  }

  /** How a filter's value reads on a chip; null for one this list does not know. */
  private labelOf(key: string, value: unknown): string | null {
    switch (key) {
      case 'variant':
        return GAME_VARIANTS.find((option) => option.value === value)?.label ?? null;
      case 'mode':
        return GAME_MODES.some((mode) => mode === value) ? `${value}` : null;
      case 'status':
        return typeof value === 'string' && Object.hasOwn(GAME_STATUS_LABELS, value)
          ? GAME_STATUS_LABELS[value as GameStatus]
          : null;
      case 'opponentId': {
        const name = this.opponents().find((player) => player.id === value)?.name;
        return name ? `Mit ${name}` : null;
      }
      case 'players':
        return typeof value === 'string' && Object.hasOwn(PLAYER_COUNTS, value)
          ? PLAYER_COUNTS[value as PlayerCount].label
          : null;
      default:
        return null;
    }
  }

  protected onSearch(query: string): void {
    this.query.set(query);
    this.games.restart();
  }

  protected open(game: GameSummaryDto): void {
    void this.router.navigate(['/account/games', game.id]);
  }

  /** Who played, "Du" for the account itself; past three only the first two and a count. */
  protected playerNames(game: GameSummaryDto): string {
    const names = game.players.map((player) => (player.isMe ? 'Du' : player.name));
    if (names.length <= 3) {
      return names.join(', ');
    }
    return `${names.slice(0, 2).join(', ')} +${names.length - 2}`;
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

  protected pickSuggestion(suggestion: FilterSuggestion): void {
    this.filters.get(suggestion.key)?.setValue(suggestion.value);
  }

  protected clearFilter(key: string): void {
    this.filters.get(key)?.reset();
  }

  /** The form as a filter. */
  private criteria(): GameFilter {
    const { variant, mode, status, opponentId, players, period, visit } =
      this.filters.getRawValue();
    const count = players ? PLAYER_COUNTS[players] : null;
    return {
      query: this.query() || null,
      variant,
      mode,
      status,
      opponentId,
      minPlayers: count?.min ?? null,
      maxPlayers: count?.max ?? null,
      ...dayRangeBounds(period),
      minVisit: visit,
    };
  }
}
