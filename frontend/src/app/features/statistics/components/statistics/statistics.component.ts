import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  LOCALE_ID,
  signal,
  untracked,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, FormsModule, ReactiveFormsModule } from '@angular/forms';
import { DatePicker } from 'primeng/datepicker';
import { Popover } from 'primeng/popover';
import { Select } from 'primeng/select';
import { SelectButton } from 'primeng/selectbutton';
import { Tab, TabList, TabPanel, TabPanels, Tabs } from 'primeng/tabs';
import { PlayerStatisticsDto } from '../../dto/player-statistics.dto';
import { StatisticsFilter } from '../../models/statistics-filter';
import {
  DEFAULT_PERIODS,
  PERIOD_CHIP_LABELS,
  STATISTICS_PERIODS,
  STATISTICS_UNITS,
  StatisticsPeriod,
  StatisticsUnit,
  periodGames,
  periodStart,
} from '../../models/statistics-period';
import { StatisticsService } from '../../services/statistics.service';
import { CHECKOUT_MODES, CheckoutMode } from '../../../game/models/checkout-mode';
import { PLAYER_COUNTS, PlayerCount } from '../../../game/models/game-filter';
import { GAME_MODES, GameMode } from '../../../game/models/game-mode';
import { PlayerIdentityDto } from '../../../player/dto/player-identity.dto';
import { PlayerService } from '../../../player/services/player.service';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { ListToolbarComponent } from '../../../../core/view/components/list-toolbar/list-toolbar.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { DayRange, dayRangeBounds, dayRangeLabel } from '../../../../core/view/models/day-range';
import {
  FilterChip,
  FilterChipOpen,
  FilterSuggestion,
} from '../../../../core/view/models/filter-chip';
import { FilterMemoryService } from '../../../../core/view/services/filter-memory.service';
import { readStored, writeStored } from '../../../../core/storage/models/browser-storage';
import {
  DAY_RANGE_PARAM,
  QueryState,
  TEXT_PARAM,
  oneOfParam,
} from '../../../../core/view/models/query-state';
import { CheckoutStatisticsComponent } from '../checkout-statistics/checkout-statistics.component';
import { PrecisionStatisticsComponent } from '../precision-statistics/precision-statistics.component';

/** The filters whose picks are remembered and offered back; the period is not among them. */
const REMEMBERED = ['opponentId', 'players', 'mode', 'checkoutMode'] as const;

type StatisticsTab = 'precision' | 'checkout';

const TABS: readonly StatisticsTab[] = ['precision', 'checkout'];

/** Where the last opened tab is kept; the view opens on it. */
const TAB_KEY = 'dart-tracking.statisticsTab';

/** How each filter is kept in the query params. */
const FILTER_PARAMS = {
  opponentId: TEXT_PARAM,
  players: oneOfParam(Object.keys(PLAYER_COUNTS) as PlayerCount[]),
  mode: oneOfParam(GAME_MODES),
  checkoutMode: oneOfParam(CHECKOUT_MODES.map((mode) => mode.value)),
};

/** Offered while the account has no picks of its own. */
const DEFAULT_SUGGESTIONS: FilterSuggestion[] = [
  { key: 'players', label: PLAYER_COUNTS.solo.label, value: 'solo' },
];

@Component({
  selector: 'app-statistics',
  imports: [
    BackLinkComponent,
    CheckoutStatisticsComponent,
    DatePicker,
    LoadingStateComponent,
    EmptyStateComponent,
    ListToolbarComponent,
    LoadErrorComponent,
    FormsModule,
    Popover,
    PrecisionStatisticsComponent,
    ReactiveFormsModule,
    Select,
    SelectButton,
    Tab,
    TabList,
    TabPanel,
    TabPanels,
    Tabs,
  ],
  templateUrl: './statistics.component.html',
  styleUrl: './statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatisticsComponent {
  private readonly statistics = inject(StatisticsService);
  private readonly players = inject(PlayerService);
  private readonly fb = inject(FormBuilder);
  private readonly locale = inject(LOCALE_ID);
  private readonly memory = inject(FilterMemoryService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly totals = signal<PlayerStatisticsDto | null>(null);
  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  private requests = 0;

  protected readonly tab = signal<StatisticsTab>(
    TABS.find((tab) => tab === readStored(TAB_KEY)) ?? 'precision',
  );

  protected readonly unitOptions = [...STATISTICS_UNITS];
  protected readonly unit = signal<StatisticsUnit>('days');
  protected readonly periodOptions = computed(() => [...STATISTICS_PERIODS[this.unit()]]);
  protected readonly period = signal<StatisticsPeriod>(DEFAULT_PERIODS.days);
  protected readonly range = signal<DayRange>(null);

  protected readonly modeOptions = GAME_MODES.map((mode) => ({ label: `${mode}`, value: mode }));
  protected readonly checkoutOptions = [...CHECKOUT_MODES];
  protected readonly playerCountOptions = Object.entries(PLAYER_COUNTS).map(([value, count]) => ({
    label: count.label,
    value: value as PlayerCount,
  }));
  protected readonly opponents = signal<PlayerIdentityDto[]>([]);

  protected readonly filters = this.fb.group({
    opponentId: this.fb.control<string | null>(null),
    players: this.fb.control<PlayerCount | null>(null),
    mode: this.fb.control<GameMode | null>(null),
    checkoutMode: this.fb.control<CheckoutMode | null>(null),
  });
  private readonly filterValue = toSignal(this.filters.valueChanges, {
    initialValue: this.filters.value,
  });
  private readonly queryState = new QueryState();

  /** The filters in use, as chips under the toolbar; the period shows in its own buttons. */
  protected readonly chips = computed<FilterChip[]>(() => {
    const value = this.filterValue();
    const period = this.period();
    const range = period === 'custom' ? dayRangeLabel(this.range(), this.locale) : null;
    return [
      {
        key: 'period',
        label: range ?? PERIOD_CHIP_LABELS[period],
        removable: false,
        opens: true,
      },
      ...REMEMBERED.flatMap((key) => {
        const picked = value[key];
        return picked ? [{ key, label: this.labelOf(key, picked) ?? 'Gegen Mitspieler' }] : [];
      }),
    ];
  });

  /** Common filters one tap away, for those still open. */
  protected readonly suggestions = computed<FilterSuggestion[]>(() => {
    const value = this.filterValue() as Record<string, unknown>;
    return this.memory.suggest(
      'statistics',
      DEFAULT_SUGGESTIONS,
      (key, picked) => this.labelOf(key, picked),
      (key) => !value[key],
    );
  });

  /** Whether anything narrows the statistics below the whole history. */
  protected readonly filtered = computed(
    () => this.period() !== 'all' || this.chips().some((chip) => chip.removable !== false),
  );

  private readonly criteria = computed<StatisticsFilter>(() => {
    const { opponentId, players, mode, checkoutMode } = this.filterValue();
    const count = players ? PLAYER_COUNTS[players] : null;
    const period = this.period();
    const bounds =
      period === 'custom'
        ? dayRangeBounds(this.range())
        : { since: periodStart(period, new Date()), until: null };
    return {
      mode: mode ?? null,
      checkoutMode: checkoutMode ?? null,
      opponentId: opponentId ?? null,
      minPlayers: count?.min ?? null,
      maxPlayers: count?.max ?? null,
      ...bounds,
      lastGames: periodGames(period),
    };
  });

  constructor() {
    this.queryState.signal(
      'unit',
      this.unit,
      oneOfParam(STATISTICS_UNITS.map((u) => u.value)),
      'days',
    );
    this.queryState.signal(
      'period',
      this.period,
      oneOfParam(Object.keys(PERIOD_CHIP_LABELS) as StatisticsPeriod[]),
      DEFAULT_PERIODS.days,
    );
    this.queryState.signal('range', this.range, DAY_RANGE_PARAM, null);
    this.queryState.form(this.filters, FILTER_PARAMS);
    void this.players.list().then((all) => this.opponents.set(all.filter((p) => !p.isSelf)));
    void this.memory.load();
    this.memory.watch('statistics', this.filters, REMEMBERED, this.destroyRef);
    effect(() => writeStored(TAB_KEY, this.tab()));
    effect(() => {
      const criteria = this.criteria();
      untracked(() => void this.load(criteria));
    });
  }

  /** How a filter's value reads on a chip; null for one this page does not know. */
  private labelOf(key: string, value: unknown): string | null {
    switch (key) {
      case 'opponentId': {
        const name = this.opponents().find((player) => player.id === value)?.name;
        return name ? `Gegen ${name}` : null;
      }
      case 'players':
        return typeof value === 'string' && Object.hasOwn(PLAYER_COUNTS, value)
          ? PLAYER_COUNTS[value as PlayerCount].label
          : null;
      case 'mode':
        return GAME_MODES.some((mode) => mode === value) ? `${value}` : null;
      case 'checkoutMode':
        return CHECKOUT_MODES.find((option) => option.value === value)?.label ?? null;
      default:
        return null;
    }
  }

  /** Switch what the quick picks count; "all" stays, any other pick starts over. */
  protected selectUnit(unit: StatisticsUnit): void {
    this.unit.set(unit);
    if (this.period() !== 'all') {
      this.period.set(DEFAULT_PERIODS[unit]);
    }
  }

  /** The period chip opens the period picker under it. */
  protected openPicker(open: FilterChipOpen, picker: Popover): void {
    if (open.key === 'period') {
      picker.toggle(open.event);
    }
  }

  /** A quick pick closes the picker; the calendar pick opens the calendar in it instead. */
  protected selectPeriod(period: StatisticsPeriod, picker: Popover): void {
    this.period.set(period);
    if (period !== 'custom') {
      picker.hide();
    }
  }

  protected pickRange(range: DayRange, calendar: Popover): void {
    this.range.set(range);
    if (range?.[1]) {
      calendar.hide();
    }
  }

  protected pickSuggestion(suggestion: FilterSuggestion): void {
    this.filters.get(suggestion.key)?.setValue(suggestion.value);
  }

  protected resetFilters(): void {
    this.filters.reset();
  }

  protected clearFilter(key: string): void {
    this.filters.get(key)?.reset();
  }

  protected reload(): void {
    void this.load(this.criteria());
  }

  /** Only the latest request may land, so a quick change of filters cannot be overtaken. */
  private async load(criteria: StatisticsFilter): Promise<void> {
    const request = ++this.requests;
    this.loading.set(true);
    this.failed.set(false);
    try {
      const totals = await this.statistics.load(criteria);
      if (request === this.requests) {
        this.totals.set(totals);
      }
    } catch {
      if (request === this.requests) {
        this.failed.set(true);
      }
    } finally {
      if (request === this.requests) {
        this.loading.set(false);
      }
    }
  }
}
