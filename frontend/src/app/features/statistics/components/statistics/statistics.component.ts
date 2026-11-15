import { DecimalPipe, NgTemplateOutlet } from '@angular/common';
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
import { Popover } from 'primeng/popover';
import { Select } from 'primeng/select';
import { Tab, TabList, TabPanel, TabPanels, Tabs } from 'primeng/tabs';
import { CricketStatisticsDto } from '../../dto/cricket-statistics.dto';
import { StatisticsOverviewDto } from '../../dto/statistics-overview.dto';
import { TargetStatisticsDto } from '../../dto/target-statistics.dto';
import { COMPARE_COLOR, Comparison, OWN_COLOR } from '../../models/comparison';
import { StatisticsFilter } from '../../models/statistics-filter';
import { GamePillsComponent } from '../game-pills/game-pills.component';
import { KillStatisticsComponent } from '../kill-statistics/kill-statistics.component';
import { KillStatisticsDto } from '../../dto/kill-statistics.dto';
import { STATISTICS_VIEWS, StatisticsGame, StatisticsView, showsPoints } from '../../models/statistics-game';
import { CRICKET_FIGURES, POINTS_FIGURES, TARGET_FIGURES } from '../../models/trend-metric';
import { OverallStatisticsComponent } from '../overall-statistics/overall-statistics.component';
import { OverallStatisticsDto } from '../../dto/overall-statistics.dto';
import { StatisticsService } from '../../services/statistics.service';
import { CHECKOUT_MODES, CheckoutMode } from '../../../game/models/checkout-mode';
import { PLAYER_COUNT_LABELS, PlayerCount } from '../../../game/models/game-filter';
import { GAME_MODES, GameMode } from '../../../game/models/game-mode';
import {
  CLOCK_ZONES,
  CRICKET_SCORINGS,
  ClockZone,
  CricketScoring,
  KILLER_ZONES,
  KillerZone,
  TRAINING_GOALS,
  TRAINING_RINGS,
  TrainingGoal,
  TrainingRing,
  scoringLabel,
} from '../../../game/models/variant-options';
import { PlayerIdentityDto } from '../../../player/dto/player-identity.dto';
import { PlayerService } from '../../../player/services/player.service';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { ListToolbarComponent } from '../../../../core/view/components/list-toolbar/list-toolbar.component';
import { FilterSelectComponent } from '../../../../core/view/components/filter-select/filter-select.component';
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
import { CricketStatisticsComponent } from '../cricket-statistics/cricket-statistics.component';
import { CheckoutStatisticsComponent } from '../checkout-statistics/checkout-statistics.component';
import { PrecisionStatisticsComponent } from '../precision-statistics/precision-statistics.component';
import { TargetStatisticsComponent } from '../target-statistics/target-statistics.component';
import { TrendStatisticsComponent } from '../trend-statistics/trend-statistics.component';
import { VisitDistributionComponent } from '../visit-distribution/visit-distribution.component';

/** The filters whose picks are remembered and offered back; the period is not among them. */
const REMEMBERED = [
  'opponentId',
  'players',
  'mode',
  'checkoutMode',
  'clockZone',
  'killerZone',
  'scoring',
  'trainingGoal',
  'trainingRing',
] as const;

type Remembered = (typeof REMEMBERED)[number];

/** The filters that are settings of one game, by the games they apply to. */
const GAME_FILTERS: Partial<Record<Remembered, readonly StatisticsView[]>> = {
  mode: ['x01', 'elimination'],
  checkoutMode: ['x01', 'elimination'],
  clockZone: ['around_the_clock'],
  killerZone: ['killer'],
  scoring: ['cricket'],
  trainingGoal: ['training'],
  trainingRing: ['training'],
};

/** The filters the game list knows too, for links into it. */
const GAME_LIST_FILTERS: readonly Remembered[] = ['opponentId', 'players', 'mode', 'checkoutMode'];

type StatisticsTab = 'precision' | 'checkout' | 'trend';

const TABS: readonly StatisticsTab[] = ['precision', 'checkout', 'trend'];

/** Where the last opened tab is kept; the view opens on it. */
const TAB_KEY = 'dart-tracking.statisticsTab';

/** How each filter is kept in the query params. */
const FILTER_PARAMS = {
  opponentId: listParam(TEXT_PARAM),
  players: listParam(oneOfParam(Object.keys(PLAYER_COUNT_LABELS) as PlayerCount[])),
  mode: listParam(oneOfParam(GAME_MODES)),
  checkoutMode: listParam(oneOfParam(CHECKOUT_MODES.map((mode) => mode.value))),
  clockZone: listParam(oneOfParam(CLOCK_ZONES.map((zone) => zone.value))),
  killerZone: listParam(oneOfParam(KILLER_ZONES.map((zone) => zone.value))),
  scoring: listParam(oneOfParam(CRICKET_SCORINGS.map((scoring) => scoring.value))),
  trainingGoal: listParam(oneOfParam(TRAINING_GOALS.map((goal) => goal.value))),
  trainingRing: listParam(oneOfParam(TRAINING_RINGS.map((ring) => ring.value))),
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
    DecimalPipe,
    NgTemplateOutlet,
    BackLinkComponent,
    Button,
    CheckoutStatisticsComponent,
    CricketStatisticsComponent,
    LoadingStateComponent,
    EmptyStateComponent,
    ListToolbarComponent,
    LoadErrorComponent,
    FormsModule,
    GamePillsComponent,
    KillStatisticsComponent,
    OverallStatisticsComponent,
    InfoHintComponent,
    FilterSelectComponent,
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
    TargetStatisticsComponent,
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
  /** The darts at targets, for the games whose figures are not points. */
  protected readonly targets = signal<TargetStatisticsDto | null>(null);
  /** Marks, visits and darts of Cricket; null for the other games. */
  protected readonly cricket = signal<CricketStatisticsDto | null>(null);
  /** Kills, for Elimination and Killer; null for the other games. */
  protected readonly kills = signal<KillStatisticsDto | null>(null);
  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  private requests = 0;

  /** The game whose figures are shown. */
  protected readonly game = signal<StatisticsView>('all');
  protected readonly gameOptions = [...STATISTICS_VIEWS];
  protected readonly points = computed(() => {
    const game = this.game();
    return game !== 'all' && showsPoints(game);
  });
  protected readonly pointsFigures = POINTS_FIGURES;
  protected readonly targetFigures = TARGET_FIGURES;
  protected readonly cricketFigures = CRICKET_FIGURES;

  /** The tab of a game at targets, which has no checkout tab: that one opens its precision. */
  protected readonly targetTab = computed(() => (this.tab() === 'trend' ? 'trend' : 'precision'));

  /** Killer's games won, for its figures; null for the other games. */
  protected readonly killerWins = computed(() => {
    const kills = this.game() === 'killer' ? this.kills() : null;
    return kills && kills.games.length > 0 ? { wins: kills.wins, games: kills.games.length } : null;
  });
  /** Every game together, for the view over all of them. */
  protected readonly overall = signal<OverallStatisticsDto | null>(null);

  /** How many games and darts the figures shown are counted from; null before they are
   * loaded or without a game. */
  protected readonly counted = computed(() => {
    if (this.failed()) {
      return null;
    }
    const points = this.points() ? this.totals() : null;
    const overall = this.game() === 'all' ? this.overall() : null;
    const other =
      this.game() === 'all'
        ? null
        : this.game() === 'cricket'
          ? this.cricket()
          : (this.kills() ?? this.targets());
    const tally = points
      ? { games: points.legs, darts: points.darts }
      : overall
        ? { games: overall.games, darts: overall.darts }
        : other && { games: other.games.length, darts: other.darts };
    return tally && tally.games > 0 ? tally : null;
  });

  protected readonly tab = signal<StatisticsTab>(
    TABS.find((tab) => tab === readStored(TAB_KEY)) ?? 'precision',
  );

  protected readonly unit = signal<PeriodUnit>('days');
  protected readonly period = signal<Period>(DEFAULT_PERIODS.days);
  protected readonly range = signal<DayRange>(null);

  protected readonly clockZoneOptions = [...CLOCK_ZONES];
  protected readonly killerZoneOptions = [...KILLER_ZONES];
  protected readonly scoringOptions = CRICKET_SCORINGS.map((option) => ({
    label: scoringLabel(option.value),
    value: option.value,
  }));
  protected readonly trainingGoalOptions = [...TRAINING_GOALS];
  protected readonly trainingRingOptions = [...TRAINING_RINGS];
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
    opponentId: this.fb.control<string[]>([], { nonNullable: true }),
    players: this.fb.control<PlayerCount[]>([], { nonNullable: true }),
    mode: this.fb.control<GameMode[]>([], { nonNullable: true }),
    checkoutMode: this.fb.control<CheckoutMode[]>([], { nonNullable: true }),
    clockZone: this.fb.control<ClockZone[]>([], { nonNullable: true }),
    killerZone: this.fb.control<KillerZone[]>([], { nonNullable: true }),
    scoring: this.fb.control<CricketScoring[]>([], { nonNullable: true }),
    trainingGoal: this.fb.control<TrainingGoal[]>([], { nonNullable: true }),
    trainingRing: this.fb.control<TrainingRing[]>([], { nonNullable: true }),
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
      ...REMEMBERED.filter((key) => this.applies(key)).flatMap((key) => {
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

  /** Loading, failed or nothing to show in the view's figures; null once they are there. */
  protected readonly status = computed<'loading' | 'failed' | 'empty' | null>(() => {
    const count = this.points()
      ? this.totals()?.legs
      : this.game() === 'all'
        ? this.overall()?.games
        : this.game() === 'cricket'
          ? this.cricket()?.darts
          : this.targets()?.darts;
    if (this.loading() && count === undefined) {
      return 'loading';
    }
    if (this.failed()) {
      return 'failed';
    }
    return count === 0 ? 'empty' : null;
  });

  /** Whether anything narrows the statistics below the whole history. */
  protected readonly filtered = computed(
    () => this.period() !== 'all' || this.chips().some((chip) => chip.removable !== false),
  );

  protected readonly criteria = computed<StatisticsFilter>(() => {
    const value = this.filterValue();
    const { opponentId, players } = value;
    const period = this.period();
    const picks = <K extends Remembered>(key: K) => (this.applies(key) ? (value[key] ?? []) : []);
    return {
      variants: this.game() === 'all' ? [] : [this.game() as StatisticsGame],
      modes: picks('mode') as GameMode[],
      checkoutModes: picks('checkoutMode') as CheckoutMode[],
      clockZones: picks('clockZone') as ClockZone[],
      killerZones: picks('killerZone') as KillerZone[],
      cricketScorings: picks('scoring') as CricketScoring[],
      trainingGoals: picks('trainingGoal') as TrainingGoal[],
      trainingRings: picks('trainingRing') as TrainingRing[],
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
    const game = this.game();
    const params: Record<string, string> = game === 'all' ? {} : { variant: game };
    for (const key of GAME_LIST_FILTERS.filter((key) => this.applies(key))) {
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
    this.queryState.signal(
      'game',
      this.game,
      oneOfParam(STATISTICS_VIEWS.map((option) => option.value)),
      'all',
    );
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
      const compared = this.points() ? this.compareId() : '';
      untracked(() => void this.load(criteria, compared));
    });
  }

  /** Whether a filter narrows the game that is shown; a setting of another game does not. */
  private applies(key: Remembered): boolean {
    return GAME_FILTERS[key]?.includes(this.game()) ?? true;
  }

  /** How a filter's picks read on a chip; null when none of them is known to this page. */
  private chipLabel(key: string, picks: readonly unknown[]): string | null {
    if (!REMEMBERED.some((known) => known === key) || !this.applies(key as Remembered)) {
      return null;
    }
    const names = picks.flatMap((pick) => this.nameOf(key as Remembered, pick) ?? []);
    if (names.length === 0) {
      return null;
    }
    return key === 'opponentId' ? $localize`:@@stats.against:Gegen ${orList(names)}:names:` : orList(names);
  }

  private nameOf(key: Remembered, value: unknown): string | null {
    switch (key) {
      case 'clockZone':
        return CLOCK_ZONES.find((option) => option.value === value)?.label ?? null;
      case 'killerZone':
        return KILLER_ZONES.find((option) => option.value === value)?.label ?? null;
      case 'scoring':
        return this.scoringOptions.find((option) => option.value === value)?.label ?? null;
      case 'trainingGoal':
        return TRAINING_GOALS.find((option) => option.value === value)?.label ?? null;
      case 'trainingRing':
        return TRAINING_RINGS.find((option) => option.value === value)?.label ?? null;
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
    void this.load(this.criteria(), this.points() ? this.compareId() : '');
  }

  /** Only the latest request may land, so a quick change of filters cannot be overtaken. */
  private async load(criteria: StatisticsFilter, compared: string): Promise<void> {
    const request = ++this.requests;
    this.loading.set(true);
    this.failed.set(false);
    try {
      const game = this.game();
      const kills =
        game === 'elimination' || game === 'killer' ? this.statistics.kills(criteria) : null;
      if (game === 'all') {
        const overall = await this.statistics.overall(criteria);
        if (request === this.requests) {
          this.overall.set(overall);
        }
      } else if (game === 'cricket') {
        const cricket = await this.statistics.cricket(criteria);
        if (request === this.requests) {
          this.cricket.set(cricket);
        }
      } else if (this.points()) {
        const [totals, others, killed] = await Promise.all([
          this.statistics.load(criteria),
          compared ? this.statistics.load(criteria, compared) : null,
          kills,
        ]);
        if (request === this.requests) {
          this.totals.set(totals);
          this.others.set(others);
          this.kills.set(killed);
        }
      } else {
        const [targets, killed] = await Promise.all([this.statistics.targets(criteria), kills]);
        if (request === this.requests) {
          this.targets.set(targets);
          this.kills.set(killed);
        }
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
