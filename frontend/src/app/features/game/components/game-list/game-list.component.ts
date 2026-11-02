import { DatePipe, formatDate } from '@angular/common';
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
import { MultiSelect } from 'primeng/multiselect';
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
  PLAYER_COUNT_LABELS,
  PlayerCount,
  VISIT_BANDS,
  VisitBand,
  visitBandLabel,
} from '../../models/game-filter';
import { CHECKOUT_MODES, CheckoutMode } from '../../models/checkout-mode';
import { GAME_MODES, GameMode } from '../../models/game-mode';
import { GAME_VARIANTS, GameVariant } from '../../models/game-variant';
import { GameHistoryService } from '../../services/game-history.service';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { ListToolbarComponent } from '../../../../core/view/components/list-toolbar/list-toolbar.component';
import { PeriodPickerComponent } from '../../../../core/view/components/period-picker/period-picker.component';
import { DayRange, dayRangeLabel } from '../../../../core/view/models/day-range';
import { backState } from '../../../../core/view/models/back-state';
import { SHORT_DATE, SHORT_DATE_TIME } from '../../../../core/i18n/models/date-format';
import {
  FilterChip,
  FilterChipOpen,
  FilterSuggestion,
  orList,
  withPick,
} from '../../../../core/view/models/filter-chip';
import { PagedTable } from '../../../../core/view/models/paged-table';
import {
  PERIOD_CHIP_LABELS,
  PERIODS,
  Period,
  periodBounds,
} from '../../../../core/view/models/period';
import {
  DAY_RANGE_PARAM,
  QueryState,
  TEXT_PARAM,
  listParam,
  oneOfParam,
} from '../../../../core/view/models/query-state';
import { FilterMemoryService } from '../../../../core/view/services/filter-memory.service';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';

/** The filters whose picks are remembered and offered back; the period is not among them. */
const REMEMBERED = ['variant', 'mode', 'checkoutMode', 'status', 'opponentId', 'players'] as const;

type Remembered = (typeof REMEMBERED)[number];

/** How each filter is kept in the query params. */
const FILTER_PARAMS = {
  variant: listParam(oneOfParam(GAME_VARIANTS.map((variant) => variant.value))),
  mode: listParam(oneOfParam(GAME_MODES)),
  checkoutMode: listParam(oneOfParam(CHECKOUT_MODES.map((mode) => mode.value))),
  status: listParam(oneOfParam(Object.keys(GAME_STATUS_LABELS) as GameStatus[])),
  opponentId: listParam(TEXT_PARAM),
  players: listParam(oneOfParam(Object.keys(PLAYER_COUNT_LABELS) as PlayerCount[])),
};

/** The quick picks by days; the list has no count of games. */
const DAY_PERIODS = PERIODS.days.map((option) => option.value);

/** Offered while the account has no picks of its own. */
const DEFAULT_SUGGESTIONS: FilterSuggestion[] = [
  { key: 'status', label: GAME_STATUS_LABELS.finished, value: 'finished' },
  { key: 'players', label: PLAYER_COUNT_LABELS.duel, value: 'duel' },
];

@Component({
  selector: 'app-game-list',
  imports: [
    BackLinkComponent,
    DatePipe,
    EmptyStateComponent,
    ListToolbarComponent,
    LoadErrorComponent,
    LoadingStateComponent,
    MultiSelect,
    PeriodPickerComponent,
    ReactiveFormsModule,
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
  protected readonly shortDate = SHORT_DATE;
  protected readonly modeOptions = GAME_MODES.map((mode) => ({ label: `${mode}`, value: mode }));
  protected readonly checkoutOptions = [...CHECKOUT_MODES];
  protected readonly statusOptions = Object.entries(GAME_STATUS_LABELS).map(([value, label]) => ({
    label,
    value: value as GameStatus,
  }));
  protected readonly playerCountOptions = Object.entries(PLAYER_COUNT_LABELS).map(
    ([value, label]) => ({ label, value: value as PlayerCount }),
  );
  protected readonly opponents = signal<PlayerIdentityDto[]>([]);
  protected readonly query = signal('');

  protected readonly period = signal<Period>('all');
  protected readonly range = signal<DayRange>(null);
  /** A visit band the statistics linked here with; it has no field of its own. */
  protected readonly visit = signal<VisitBand | null>(null);

  protected readonly filters = this.fb.group({
    variant: this.fb.control<GameVariant[]>([], { nonNullable: true }),
    mode: this.fb.control<GameMode[]>([], { nonNullable: true }),
    checkoutMode: this.fb.control<CheckoutMode[]>([], { nonNullable: true }),
    status: this.fb.control<GameStatus[]>([], { nonNullable: true }),
    opponentId: this.fb.control<string[]>([], { nonNullable: true }),
    players: this.fb.control<PlayerCount[]>([], { nonNullable: true }),
  });
  private readonly queryState = new QueryState();

  protected readonly games = new PagedTable<GameSummaryDto>((limit, offset) =>
    this.history.list(limit, offset, this.criteria()),
  );

  private readonly filterValue = toSignal(this.filters.valueChanges, {
    initialValue: this.filters.value,
  });
  /** The filters in use, as chips above the table; the period shows in its own picker. */
  protected readonly chips = computed<FilterChip[]>(() => {
    const value = this.filterValue();
    const period = this.period();
    const range = period === 'custom' ? dayRangeLabel(this.range(), this.locale) : null;
    const chips: FilterChip[] = [
      { key: 'period', label: range ?? PERIOD_CHIP_LABELS[period], removable: false, opens: true },
    ];
    for (const key of REMEMBERED) {
      const label = this.chipLabel(key, value[key] ?? []);
      if (label) {
        chips.push({ key, label });
      }
    }
    const visit = this.visit();
    if (visit) {
      chips.push({ key: 'visit', label: $localize`:@@game.list.with:Mit ${visitBandLabel(visit)}:what:` });
    }
    return chips;
  });
  /** Common filters one tap away, for those still open. */
  protected readonly suggestions = computed<FilterSuggestion[]>(() => {
    const value = this.filterValue() as Record<string, unknown[] | undefined>;
    return this.memory.suggest(
      'games',
      DEFAULT_SUGGESTIONS,
      (key, picked) => this.chipLabel(key, [picked]),
      (key, picked) => !(value[key] ?? []).includes(picked),
    );
  });
  /** Whether the search or a filter narrows the list. */
  protected readonly filtered = computed(
    () =>
      this.query() !== '' ||
      this.period() !== 'all' ||
      this.chips().some((chip) => chip.removable !== false),
  );

  constructor() {
    this.queryState.signal('period', this.period, oneOfParam(DAY_PERIODS), 'all');
    this.queryState.signal('range', this.range, DAY_RANGE_PARAM, null);
    this.queryState.signal('visit', this.visit, oneOfParam<VisitBand>(VISIT_BANDS), null);
    this.queryState.form(this.filters, FILTER_PARAMS);
    void this.games.load();
    void this.players.list().then((all) => this.opponents.set(all.filter((p) => !p.isSelf)));
    void this.memory.load();
    this.memory.watch('games', this.filters, REMEMBERED, this.destroyRef);
    this.filters.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => this.games.restart());
  }

  /** How a filter's picks read on a chip; null when none of them is known to this list. */
  private chipLabel(key: string, picks: readonly unknown[]): string | null {
    const names = picks.flatMap((pick) => this.nameOf(key as Remembered, pick) ?? []);
    if (names.length === 0) {
      return null;
    }
    return key === 'opponentId' ? $localize`:@@game.list.with:Mit ${orList(names)}:what:` : orList(names);
  }

  private nameOf(key: Remembered, value: unknown): string | null {
    switch (key) {
      case 'variant':
        return GAME_VARIANTS.find((option) => option.value === value)?.label ?? null;
      case 'mode':
        return GAME_MODES.some((mode) => mode === value) ? `${value}` : null;
      case 'checkoutMode':
        return CHECKOUT_MODES.find((option) => option.value === value)?.label ?? null;
      case 'status':
        return typeof value === 'string' && Object.hasOwn(GAME_STATUS_LABELS, value)
          ? GAME_STATUS_LABELS[value as GameStatus]
          : null;
      case 'opponentId':
        return this.opponents().find((player) => player.id === value)?.name ?? null;
      case 'players':
        return typeof value === 'string' && Object.hasOwn(PLAYER_COUNT_LABELS, value)
          ? PLAYER_COUNT_LABELS[value as PlayerCount]
          : null;
    }
  }

  protected onSearch(query: string): void {
    this.query.set(query);
    this.games.restart();
  }

  protected open(game: GameSummaryDto): void {
    void this.router.navigate(['/account/games', game.id], {
      state: backState($localize`:@@auth.account.games:Spiele`),
    });
  }

  protected openLabel(game: GameSummaryDto): string {
    const when = formatDate(game.createdAt, SHORT_DATE_TIME, this.locale);
    return $localize`:@@game.list.open:Spiel vom ${when}:date: öffnen`;
  }

  /** Who played, "You" for the account itself; past three only the first two and a count. */
  protected playerNames(game: GameSummaryDto): string {
    const names = game.players.map((player) =>
      player.isMe ? $localize`:@@player.list.self:Du` : player.name,
    );
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
    this.setVisit(null);
  }

  protected pickSuggestion(suggestion: FilterSuggestion): void {
    const control = this.filters.get(suggestion.key);
    control?.setValue(withPick(control.value as unknown[], suggestion.value));
  }

  protected clearFilter(key: string): void {
    if (key === 'visit') {
      this.setVisit(null);
    } else {
      this.filters.get(key)?.reset();
    }
  }

  /** The period chip opens the period picker under it. */
  protected openPicker(open: FilterChipOpen, picker: PeriodPickerComponent): void {
    if (open.key === 'period') {
      picker.toggle(open.event);
    }
  }

  protected setPeriod(period: Period): void {
    this.period.set(period);
    this.games.restart();
  }

  protected setRange(range: DayRange): void {
    this.range.set(range);
    this.games.restart();
  }

  private setVisit(visit: VisitBand | null): void {
    this.visit.set(visit);
    this.games.restart();
  }

  /** The form as a filter. */
  private criteria(): GameFilter {
    const { variant, mode, checkoutMode, status, opponentId, players } = this.filters.getRawValue();
    return {
      query: this.query() || null,
      variants: variant,
      modes: mode,
      checkoutModes: checkoutMode,
      statuses: status,
      opponentIds: opponentId,
      playerCounts: players,
      ...periodBounds(this.period(), this.range(), new Date()),
      minVisit: this.visit(),
    };
  }
}
