import { DatePipe, DecimalPipe, NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  LOCALE_ID,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, FormsModule, ReactiveFormsModule } from '@angular/forms';
import { MultiSelect } from 'primeng/multiselect';
import { Select } from 'primeng/select';
import { AccuracySummaryDto, FieldKind, GameAccuracyDto } from '../../dto/accuracy.dto';
import { EvaluationFilter, RUN_KIND_LABELS, RunKind } from '../../models/evaluation-filter';
import { EvaluationService } from '../../services/evaluation.service';
import { GAME_MODES, GameMode } from '../../../game/models/game-mode';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { ListToolbarComponent } from '../../../../core/view/components/list-toolbar/list-toolbar.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
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
  PERIOD_CHIP_LABELS,
  PERIODS,
  Period,
  periodBounds,
} from '../../../../core/view/models/period';
import {
  DAY_RANGE_PARAM,
  QueryParam,
  QueryState,
  listParam,
  oneOfParam,
} from '../../../../core/view/models/query-state';
import { FilterMemoryService } from '../../../../core/view/services/filter-memory.service';

/** What the outcome counts are called on the page, in reading order. */
const OUTCOMES: readonly { key: keyof AccuracySummaryDto; label: string; hint: string }[] = [
  { key: 'correct', label: 'Korrekt', hint: 'Im richtigen Segment gebucht' },
  { key: 'wrong', label: 'Falsch', hint: 'Gebucht, aber im falschen Segment' },
  { key: 'missed', label: 'Verpasst', hint: 'Geworfen, von der Kamera nie gebucht' },
  { key: 'phantom', label: 'Phantom', hint: 'Gebucht, ohne dass ein Pfeil steckte' },
];

const FIELD_LABELS: Record<FieldKind, string> = {
  single: 'Single',
  double: 'Double',
  triple: 'Triple',
  outside: 'Daneben',
};

/** The filters whose picks are remembered and offered back; version and period are not. */
const REMEMBERED = ['mode', 'run'] as const;

/** Tracker versions as `5,4`, or `all` for every one, so a cleared pick survives a reload. */
const VERSIONS_PARAM: QueryParam<number[]> = {
  parse: (raw) => {
    const versions = raw.split(',').map(Number);
    return raw === 'all' ? [] : versions.every(Number.isInteger) ? versions : undefined;
  },
  format: (versions) => (versions.length === 0 ? 'all' : versions.join(',')),
};

/** How each filter is kept in the query params. */
const FILTER_PARAMS = {
  version: VERSIONS_PARAM,
  mode: listParam(oneOfParam(GAME_MODES)),
  run: oneOfParam(Object.keys(RUN_KIND_LABELS) as RunKind[]),
};

/** Offered while the account has no picks of its own. */
const DEFAULT_SUGGESTIONS: FilterSuggestion[] = [
  { key: 'run', label: RUN_KIND_LABELS.test, value: 'test' },
];

interface ScopeOption {
  readonly gameId: string | null;
  readonly label: string;
}

@Component({
  selector: 'app-evaluation',
  imports: [
    BackLinkComponent,
    DecimalPipe,
    FormsModule,
    ListToolbarComponent,
    LoadErrorComponent,
    LoadingStateComponent,
    MultiSelect,
    NgTemplateOutlet,
    EmptyStateComponent,
    PeriodPickerComponent,
    ReactiveFormsModule,
    Select,
  ],
  templateUrl: './evaluation.component.html',
  styleUrl: './evaluation.component.scss',
  providers: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EvaluationComponent {
  private readonly evaluation = inject(EvaluationService);
  private readonly dates = inject(DatePipe);
  private readonly fb = inject(FormBuilder);
  private readonly locale = inject(LOCALE_ID);
  private readonly memory = inject(FilterMemoryService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly total = signal<AccuracySummaryDto | null>(null);
  protected readonly games = signal<readonly GameAccuracyDto[]>([]);
  protected readonly selectedGameId = signal<string | null>(null);
  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  private requests = 0;

  protected readonly outcomes = OUTCOMES;
  protected readonly fieldLabels = FIELD_LABELS;

  /** Tracker versions there are games of, newest first; null until they are known. */
  protected readonly versions = signal<number[] | null>(null);
  /** The known versions plus any the URL picked, so a pick always has its label. */
  protected readonly versionOptions = computed(() =>
    [...new Set([...(this.versions() ?? []), ...(this.filterValue().version ?? [])])]
      .sort((a, b) => b - a)
      .map((version) => ({ label: `v${version}`, value: version })),
  );
  protected readonly modeOptions = GAME_MODES.map((mode) => ({ label: `${mode}`, value: mode }));
  protected readonly runOptions = Object.entries(RUN_KIND_LABELS).map(([value, label]) => ({
    label,
    value: value as RunKind,
  }));

  protected readonly period = signal<Period>('all');
  protected readonly range = signal<DayRange>(null);

  protected readonly filters = this.fb.group({
    version: this.fb.control<number[] | null>(null),
    mode: this.fb.control<GameMode[]>([], { nonNullable: true }),
    run: this.fb.control<RunKind | null>(null),
  });
  private readonly filterValue = toSignal(this.filters.valueChanges, {
    initialValue: this.filters.value,
  });
  private readonly queryState = new QueryState();

  /** The filters in use, as chips above the figures; the period shows in its own picker. */
  protected readonly chips = computed<FilterChip[]>(() => {
    const { version, mode, run } = this.filterValue();
    const period = this.period();
    const range = period === 'custom' ? dayRangeLabel(this.range(), this.locale) : null;
    const chips: FilterChip[] = [
      { key: 'period', label: range ?? PERIOD_CHIP_LABELS[period], removable: false, opens: true },
    ];
    if (version?.length) {
      chips.push({ key: 'version', label: `Tracker ${orList(version.map((v) => `v${v}`))}` });
    }
    const modes = this.chipLabel('mode', mode ?? []);
    if (modes) {
      chips.push({ key: 'mode', label: modes });
    }
    if (run) {
      chips.push({ key: 'run', label: RUN_KIND_LABELS[run] });
    }
    return chips;
  });

  /** Common filters one tap away, for those still open. */
  protected readonly suggestions = computed<FilterSuggestion[]>(() => {
    const { mode, run } = this.filterValue();
    return this.memory.suggest(
      'evaluation',
      DEFAULT_SUGGESTIONS,
      (key, picked) => this.chipLabel(key, [picked]),
      (key, picked) => (key === 'mode' ? !(mode ?? []).some((m) => m === picked) : !run),
    );
  });

  /** Whether anything narrows the games below every logged one. */
  protected readonly filtered = computed(
    () => this.period() !== 'all' || this.chips().some((chip) => chip.removable !== false),
  );

  /** Null until the default version is in, so the page never loads every version first. */
  private readonly criteria = computed<EvaluationFilter | null>(() => {
    const { version, mode, run } = this.filterValue();
    if (version === null || version === undefined) {
      return null;
    }
    return {
      versions: version,
      modes: mode ?? [],
      testRun: run ? run === 'test' : null,
      ...periodBounds(this.period(), this.range(), new Date()),
    };
  });

  /** The whole set first, then one entry per logged game, newest first. */
  protected readonly scopes = computed<ScopeOption[]>(() => [
    {
      gameId: null,
      label: `Gesamt (${this.games().length} ${this.games().length === 1 ? 'Spiel' : 'Spiele'})`,
    },
    ...this.games().map((game) => ({
      gameId: game.gameId,
      label: this.labelOf(game),
    })),
  ]);

  protected readonly selectedGame = computed<GameAccuracyDto | null>(() => {
    const gameId = this.selectedGameId();
    return this.games().find((game) => game.gameId === gameId) ?? null;
  });

  protected readonly summary = computed<AccuracySummaryDto | null>(() =>
    this.selectedGameId() === null ? this.total() : (this.selectedGame()?.summary ?? null),
  );

  /** Share of thrown darts booked in the right segment. */
  protected readonly accuracy = computed(() => {
    const summary = this.summary();
    return !summary || summary.dartsThrown === 0 ? null : summary.correct / summary.dartsThrown;
  });

  protected readonly cleanVisitRate = computed(() => {
    const summary = this.summary();
    return !summary || summary.visits === 0 ? null : summary.cleanVisits / summary.visits;
  });

  constructor() {
    this.queryState.signal(
      'period',
      this.period,
      oneOfParam(PERIODS.days.map((option) => option.value)),
      'all',
    );
    this.queryState.signal('range', this.range, DAY_RANGE_PARAM, null);
    this.queryState.form(this.filters, FILTER_PARAMS);
    void this.memory.load();
    this.memory.watch('evaluation', this.filters, REMEMBERED, this.destroyRef);
    void this.loadVersions();
    effect(() => {
      const criteria = this.criteria();
      if (criteria) {
        untracked(() => void this.load(criteria));
      }
    });
  }

  /** Every judged dart, phantoms included: the base of the outcome shares. */
  protected readonly judged = computed(() => {
    const summary = this.summary();
    return summary ? summary.correct + summary.wrong + summary.missed + summary.phantom : 0;
  });

  protected share(count: number): number | null {
    const judged = this.judged();
    return judged === 0 ? null : count / judged;
  }

  protected count(key: keyof AccuracySummaryDto): number {
    return (this.summary()?.[key] as number) ?? 0;
  }

  protected sideOf(degrees: number, negative: string, positive: string): string {
    const rounded = Math.round(Math.abs(degrees));
    return `${rounded}° ${degrees < 0 ? negative : positive}`;
  }

  /** How a filter's picks read on a chip; null when none of them is known to this page. */
  private chipLabel(key: string, picks: readonly unknown[]): string | null {
    const names = picks.flatMap((pick) => {
      if (key === 'mode') {
        return GAME_MODES.some((mode) => mode === pick) ? [`${pick}`] : [];
      }
      return key === 'run' && typeof pick === 'string' && Object.hasOwn(RUN_KIND_LABELS, pick)
        ? [RUN_KIND_LABELS[pick as RunKind]]
        : [];
    });
    return names.length === 0 ? null : orList(names);
  }

  private labelOf(game: GameAccuracyDto): string {
    const date = this.dates.transform(game.createdAt, 'dd.MM.yy HH:mm') ?? '';
    const marker = game.evaluationEnabled ? ' · Testlauf' : '';
    return `${date} · ${game.mode}${marker}`;
  }

  /** The period chip opens the period picker under it. */
  protected openPicker(open: FilterChipOpen, picker: PeriodPickerComponent): void {
    if (open.key === 'period') {
      picker.toggle(open.event);
    }
  }

  protected pickSuggestion(suggestion: FilterSuggestion): void {
    if (suggestion.key === 'mode') {
      const control = this.filters.controls.mode;
      control.setValue(withPick(control.value, suggestion.value as GameMode));
    } else {
      this.filters.get(suggestion.key)?.setValue(suggestion.value);
    }
  }

  /** Back to the newest version and nothing else narrowed but the period. */
  protected resetFilters(): void {
    this.filters.reset({ version: this.newest() });
  }

  /** Removing the version chip shows every version, which the URL keeps as `all`. */
  protected clearFilter(key: string): void {
    if (key === 'version') {
      this.filters.controls.version.setValue([]);
    } else {
      this.filters.get(key)?.reset();
    }
  }

  protected retry(): void {
    const criteria = this.criteria();
    if (criteria) {
      void this.load(criteria);
    } else {
      void this.loadVersions();
    }
  }

  private newest(): number[] {
    const newest = this.versions()?.[0];
    return newest === undefined ? [] : [newest];
  }

  /** The versions first, then the newest one as the default unless the URL picked others. */
  private async loadVersions(): Promise<void> {
    this.loading.set(true);
    this.failed.set(false);
    try {
      this.versions.set(await this.evaluation.loadVersions());
      if (this.filters.controls.version.value === null) {
        this.filters.controls.version.setValue(this.newest());
      }
    } catch {
      this.failed.set(true);
      this.loading.set(false);
    }
  }

  /** Only the latest request may land, so a quick change of filters cannot be overtaken. */
  private async load(criteria: EvaluationFilter): Promise<void> {
    const request = ++this.requests;
    this.loading.set(true);
    this.failed.set(false);
    try {
      const report = await this.evaluation.loadAccuracy(criteria);
      if (request === this.requests) {
        this.total.set(report.total);
        this.games.set(report.games);
        if (!report.games.some((game) => game.gameId === this.selectedGameId())) {
          this.selectedGameId.set(null);
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
