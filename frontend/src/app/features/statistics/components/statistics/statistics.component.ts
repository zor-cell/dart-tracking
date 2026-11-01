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
import { Params } from '@angular/router';
import { Button } from 'primeng/button';
import { MultiSelect } from 'primeng/multiselect';
import { Popover } from 'primeng/popover';
import { Select } from 'primeng/select';
import { Tab, TabList, TabPanel, TabPanels, Tabs } from 'primeng/tabs';
import { StatisticsOverviewDto } from '../../dto/statistics-overview.dto';
import { COMPARE_COLOR, Comparison, OWN_COLOR } from '../../models/comparison';
import { StatisticsFilter } from '../../models/statistics-filter';
import { StatisticsService } from '../../services/statistics.service';
import { CHECKOUT_MODES, CheckoutMode } from '../../../game/models/checkout-mode';
import { PLAYER_COUNT_LABELS, PlayerCount } from '../../../game/models/game-filter';
import { GAME_MODES, GameMode } from '../../../game/models/game-mode';
import { GAME_VARIANTS, GameVariant } from '../../../game/models/game-variant';
import { PlayerIdentityDto } from '../../../player/dto/player-identity.dto';
import { PlayerService } from '../../../player/services/player.service';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { ListToolbarComponent } from '../../../../core/view/components/list-toolbar/list-toolbar.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { PeriodPickerComponent } from '../../../../core/view/components/period-picker/period-picker.component';
import { DayRange, dayRangeLabel } from '../../../../core/view/models/day-range';
import {
  FilterChip,
  FilterChipOpen,
  FilterSuggestion,
  orList,
  withPick,
} from '../../../../core/view/models/filter-chip';
import {
  DEFAULT_PERIODS,
  PERIOD_CHIP_LABELS,
  PERIOD_UNITS,
  PERIODS,
  Period,
  PeriodUnit,
  periodBounds,
  periodGames,
} from '../../../../core/view/models/period';
import { centrePopoverArrow } from '../../../../core/view/models/popover-arrow';
import { FilterMemoryService } from '../../../../core/view/services/filter-memory.service';
import { readStored, writeStored } from '../../../../core/storage/models/browser-storage';
import {
  DAY_RANGE_PARAM,
  QueryState,
  TEXT_PARAM,
  listParam,
  oneOfParam,
} from '../../../../core/view/models/query-state';
import { CheckoutStatisticsComponent } from '../checkout-statistics/checkout-statistics.component';
import { PrecisionStatisticsComponent } from '../precision-statistics/precision-statistics.component';
import { TrendStatisticsComponent } from '../trend-statistics/trend-statistics.component';
import { VisitDistributionComponent } from '../visit-distribution/visit-distribution.component';

/** The filters whose picks are remembered and offered back; the period is not among them. */
const REMEMBERED = ['variant', 'opponentId', 'players', 'mode', 'checkoutMode'] as const;

type Remembered = (typeof REMEMBERED)[number];

type StatisticsTab = 'precision' | 'checkout' | 'trend';

const TABS: readonly StatisticsTab[] = ['precision', 'checkout', 'trend'];

/** Where the last opened tab is kept; the view opens on it. */
const TAB_KEY = 'dart-tracking.statisticsTab';

/** How each filter is kept in the query params. */
const FILTER_PARAMS = {
  variant: listParam(oneOfParam(GAME_VARIANTS.map((variant) => variant.value))),
  opponentId: listParam(TEXT_PARAM),
  players: listParam(oneOfParam(Object.keys(PLAYER_COUNT_LABELS) as PlayerCount[])),
  mode: listParam(oneOfParam(GAME_MODES)),
  checkoutMode: listParam(oneOfParam(CHECKOUT_MODES.map((mode) => mode.value))),
};

/** The quick picks the game list knows too; a count of games has no counterpart there. */
const DAY_PERIODS: readonly Period[] = PERIODS.days.map((option) => option.value);

/** Offered while the account has no picks of its own. */
const DEFAULT_SUGGESTIONS: FilterSuggestion[] = [
  { key: 'players', label: PLAYER_COUNT_LABELS.solo, value: 'solo' },
];

@Component({
  selector: 'app-statistics',
  imports: [
    BackLinkComponent,
    Button,
    CheckoutStatisticsComponent,
    LoadingStateComponent,
    EmptyStateComponent,
    ListToolbarComponent,
    LoadErrorComponent,
    FormsModule,
    InfoHintComponent,
    MultiSelect,
    PeriodPickerComponent,
    Popover,
    PrecisionStatisticsComponent,
    ReactiveFormsModule,
    Select,
    Tab,
    TabList,
    TabPanel,
    TabPanels,
    Tabs,
    TrendStatisticsComponent,
    VisitDistributionComponent,
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

  protected readonly totals = signal<StatisticsOverviewDto | null>(null);
  /** The compared player's figures under the same filters, null while nobody is compared. */
  protected readonly others = signal<StatisticsOverviewDto | null>(null);
  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  private requests = 0;

  protected readonly tab = signal<StatisticsTab>(
    TABS.find((tab) => tab === readStored(TAB_KEY)) ?? 'precision',
  );

  protected readonly unit = signal<PeriodUnit>('days');
  protected readonly period = signal<Period>(DEFAULT_PERIODS.days);
  protected readonly range = signal<DayRange>(null);

  protected readonly variantOptions = [...GAME_VARIANTS];
  protected readonly modeOptions = GAME_MODES.map((mode) => ({ label: `${mode}`, value: mode }));
  protected readonly checkoutOptions = [...CHECKOUT_MODES];
  protected readonly playerCountOptions = Object.entries(PLAYER_COUNT_LABELS).map(
    ([value, label]) => ({ label, value: value as PlayerCount }),
  );
  protected readonly opponents = signal<PlayerIdentityDto[]>([]);

  /** The address book entry set beside one's own figures; empty for none. */
  protected readonly compareId = signal('');
  protected readonly ownColor = OWN_COLOR;
  protected readonly compareColor = COMPARE_COLOR;
  protected readonly comparedPlayer = computed(
    () => this.opponents().find((player) => player.id === this.compareId()) ?? null,
  );
  /** Handed to the tabs only once the compared player has a counted game. */
  protected readonly comparison = computed<Comparison | null>(() => {
    const player = this.comparedPlayer();
    const statistics = this.others();
    return player && statistics && statistics.legs > 0 ? { name: player.name, statistics } : null;
  });

  protected readonly filters = this.fb.group({
    variant: this.fb.control<GameVariant[]>([], { nonNullable: true }),
    opponentId: this.fb.control<string[]>([], { nonNullable: true }),
    players: this.fb.control<PlayerCount[]>([], { nonNullable: true }),
    mode: this.fb.control<GameMode[]>([], { nonNullable: true }),
    checkoutMode: this.fb.control<CheckoutMode[]>([], { nonNullable: true }),
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
        const label = this.chipLabel(key, value[key] ?? []);
        return label ? [{ key, label }] : [];
      }),
    ];
  });

  /** Common filters one tap away, for those still open. */
  protected readonly suggestions = computed<FilterSuggestion[]>(() => {
    const value = this.filterValue() as Record<string, unknown[] | undefined>;
    return this.memory.suggest(
      'statistics',
      DEFAULT_SUGGESTIONS,
      (key, picked) => this.chipLabel(key, [picked]),
      (key, picked) => !(value[key] ?? []).includes(picked),
    );
  });

  /** Whether anything narrows the statistics below the whole history. */
  protected readonly filtered = computed(
    () => this.period() !== 'all' || this.chips().some((chip) => chip.removable !== false),
  );

  protected readonly criteria = computed<StatisticsFilter>(() => {
    const { variant, opponentId, players, mode, checkoutMode } = this.filterValue();
    const period = this.period();
    return {
      variants: variant ?? [],
      modes: mode ?? [],
      checkoutModes: checkoutMode ?? [],
      opponentIds: opponentId ?? [],
      playerCounts: players ?? [],
      ...periodBounds(period, this.range(), new Date()),
      lastGames: periodGames(period),
    };
  });

  /** The filters as the game list reads them, for links into it. A count of recent games
   * has no counterpart there, so that period is left out. */
  protected readonly gameListParams = computed<Params>(() => {
    const value = this.filterValue();
    const params: Record<string, string> = {};
    for (const key of REMEMBERED) {
      const picks = (value[key] ?? []) as never[];
      if (picks.length > 0) {
        params[key] = FILTER_PARAMS[key].format(picks);
      }
    }
    const period = this.period();
    if (period !== 'all' && DAY_PERIODS.includes(period)) {
      params['period'] = period;
    }
    const range = period === 'custom' ? DAY_RANGE_PARAM.format(this.range()) : '';
    if (range) {
      params['range'] = range;
    }
    return params;
  });

  constructor() {
    this.queryState.signal('unit', this.unit, oneOfParam(PERIOD_UNITS.map((u) => u.value)), 'days');
    this.queryState.signal(
      'period',
      this.period,
      oneOfParam(Object.keys(PERIOD_CHIP_LABELS) as Period[]),
      DEFAULT_PERIODS.days,
    );
    this.queryState.signal('range', this.range, DAY_RANGE_PARAM, null);
    this.queryState.form(this.filters, FILTER_PARAMS);
    this.queryState.signal('compare', this.compareId, TEXT_PARAM, '');
    void this.players.list().then((all) => {
      const others = all.filter((p) => !p.isSelf);
      this.opponents.set(others);
      if (!others.some((player) => player.id === this.compareId())) {
        this.compareId.set('');
      }
    });
    void this.memory.load();
    this.memory.watch('statistics', this.filters, REMEMBERED, this.destroyRef);
    effect(() => writeStored(TAB_KEY, this.tab()));
    effect(() => {
      const criteria = this.criteria();
      const compared = this.compareId();
      untracked(() => void this.load(criteria, compared));
    });
  }

  /** How a filter's picks read on a chip; null when none of them is known to this page. */
  private chipLabel(key: string, picks: readonly unknown[]): string | null {
    const names = picks.flatMap((pick) => this.nameOf(key as Remembered, pick) ?? []);
    if (names.length === 0) {
      return null;
    }
    return key === 'opponentId' ? `Gegen ${orList(names)}` : orList(names);
  }

  private nameOf(key: Remembered, value: unknown): string | null {
    switch (key) {
      case 'variant':
        return GAME_VARIANTS.find((option) => option.value === value)?.label ?? null;
      case 'opponentId':
        return this.opponents().find((player) => player.id === value)?.name ?? null;
      case 'players':
        return typeof value === 'string' && Object.hasOwn(PLAYER_COUNT_LABELS, value)
          ? PLAYER_COUNT_LABELS[value as PlayerCount]
          : null;
      case 'mode':
        return GAME_MODES.some((mode) => mode === value) ? `${value}` : null;
      case 'checkoutMode':
        return CHECKOUT_MODES.find((option) => option.value === value)?.label ?? null;
    }
  }

  /** The period chip opens the period picker under it. */
  protected openPicker(open: FilterChipOpen, picker: PeriodPickerComponent): void {
    if (open.key === 'period') {
      picker.toggle(open.event);
    }
  }

  protected pickSuggestion(suggestion: FilterSuggestion): void {
    const control = this.filters.get(suggestion.key);
    control?.setValue(withPick(control.value as unknown[], suggestion.value));
  }

  protected resetFilters(): void {
    this.filters.reset();
  }

  protected clearFilter(key: string): void {
    this.filters.get(key)?.reset();
  }

  protected centreArrow(picker: Popover): void {
    centrePopoverArrow(picker);
  }

  /** Picks whom to compare with, or nobody, and closes the picker. */
  protected pickCompared(id: string | null, picker: Popover): void {
    this.compareId.set(id ?? '');
    picker.hide();
  }

  protected reload(): void {
    void this.load(this.criteria(), this.compareId());
  }

  /** Only the latest request may land, so a quick change of filters cannot be overtaken. */
  private async load(criteria: StatisticsFilter, compared: string): Promise<void> {
    const request = ++this.requests;
    this.loading.set(true);
    this.failed.set(false);
    try {
      const [totals, others] = await Promise.all([
        this.statistics.load(criteria),
        compared ? this.statistics.load(criteria, compared) : null,
      ]);
      if (request === this.requests) {
        this.totals.set(totals);
        this.others.set(others);
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
