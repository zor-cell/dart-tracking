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
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, FormsModule, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MenuItem } from 'primeng/api';
import { Button } from 'primeng/button';
import { Menu } from 'primeng/menu';
import { MultiSelect } from 'primeng/multiselect';
import { Select } from 'primeng/select';
import { Slider } from 'primeng/slider';
import { Tab, TabList, TabPanel, TabPanels, Tabs } from 'primeng/tabs';
import {
  AccuracySummaryDto,
  FailureCountDto,
  GameAccuracyDto,
  GroupBreakdownDto,
  GroupKind,
  MismatchDto,
  TipDto,
} from '../../dto/accuracy.dto';
import { ChartGroup } from '../../models/chart-parts';
import { GROUP_KINDS, groupLabel } from '../../models/evaluation-groups';
import { AccuracyChartsComponent } from '../accuracy-charts/accuracy-charts.component';
import { AccuracySummaryComponent } from '../accuracy-summary/accuracy-summary.component';
import { AccuracyTrendComponent } from '../accuracy-trend/accuracy-trend.component';
import { GameTableComponent } from '../game-table/game-table.component';
import { GroupChartsComponent } from '../group-charts/group-charts.component';
import { MismatchTableComponent } from '../mismatch-table/mismatch-table.component';
import {
  EvaluationFilter,
  RUN_KIND_LABELS,
  RunKind,
  TILT_LIMITS,
  TiltRange,
  VersionRange,
} from '../../models/evaluation-filter';
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
import { backState } from '../../../../core/view/models/back-state';

/** "54", "52–54", "from 52", "to 54"; null for every version. */
function versionLabel([from, to]: VersionRange): string | null {
  if (from === null && to === null) {
    return null;
  }
  if (from === to) {
    return `${from}`;
  }
  if (from === null) {
    return $localize`:@@eval.upTo:bis ${to}:version:`;
  }
  return to === null ? $localize`:@@eval.since:ab ${from}:version:` : `${from}–${to}`;
}

/** The filters whose picks are remembered and offered back; version and period are not. */
const REMEMBERED = ['mode', 'run'] as const;

/** A range as `4-6`, `5` for one value, `4-` or `-6` for an open end. */
function rangeParam(parse: (raw: string) => number): QueryParam<[number | null, number | null]> {
  const bound = (raw: string) => (raw === '' ? null : parse(raw));
  return {
    parse: (raw) => {
      const [from, to = from] = raw.split('-').map(bound);
      const valid = [from, to].every((end) => end === null || Number.isFinite(end));
      return valid && (from !== null || to !== null) ? [from, to] : undefined;
    },
    format: ([from, to]) => (from === to ? `${from ?? ''}` : `${from ?? ''}-${to ?? ''}`),
  };
}

const VERSION_RANGE_PARAM = rangeParam(Number);

/** The version range, or `all` for every version, so a cleared pick survives a reload. */
const VERSION_PARAM: QueryParam<[number | null, number | null]> = {
  parse: (raw) => (raw === 'all' ? [null, null] : VERSION_RANGE_PARAM.parse(raw)),
  format: (range) =>
    range[0] === null && range[1] === null ? 'all' : VERSION_RANGE_PARAM.format(range),
};

/** How each filter is kept in the query params. */
const FILTER_PARAMS = {
  version: VERSION_PARAM,
  mode: listParam(oneOfParam(GAME_MODES)),
  run: oneOfParam(Object.keys(RUN_KIND_LABELS) as RunKind[]),
  tilt: rangeParam(Number) as QueryParam<unknown>,
};

/** Milliseconds the tilt slider rests before its range is applied. */
const TILT_DEBOUNCE_MS = 300;

/** Offered while the account has no picks of its own. */
const DEFAULT_SUGGESTIONS: FilterSuggestion[] = [
  { key: 'run', label: RUN_KIND_LABELS.test, value: 'test' },
];

/** The tabs of the page, kept in the URL so a game opened from one leads back to it. */
const TABS = ['overview', 'analysis', 'games'] as const;
type EvaluationTab = (typeof TABS)[number];

@Component({
  selector: 'app-evaluation',
  imports: [
    AccuracyChartsComponent,
    AccuracySummaryComponent,
    AccuracyTrendComponent,
    BackLinkComponent,
    Button,
    GameTableComponent,
    GroupChartsComponent,
    MismatchTableComponent,
    FormsModule,
    ListToolbarComponent,
    LoadErrorComponent,
    LoadingStateComponent,
    Menu,
    MultiSelect,
    EmptyStateComponent,
    PeriodPickerComponent,
    ReactiveFormsModule,
    Select,
    Slider,
    Tab,
    TabList,
    TabPanel,
    TabPanels,
    Tabs,
  ],
  templateUrl: './evaluation.component.html',
  styleUrl: './evaluation.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EvaluationComponent {
  private readonly evaluation = inject(EvaluationService);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder);
  private readonly locale = inject(LOCALE_ID);
  private readonly memory = inject(FilterMemoryService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly total = signal<AccuracySummaryDto | null>(null);
  protected readonly games = signal<readonly GameAccuracyDto[]>([]);
  protected readonly groups = signal<readonly GroupBreakdownDto[]>([]);
  protected readonly failures = signal<readonly FailureCountDto[]>([]);
  protected readonly mismatches = signal<readonly MismatchDto[]>([]);
  protected readonly tips = signal<readonly TipDto[]>([]);
  protected readonly tab = signal<EvaluationTab>('overview');
  /** What the analysis splits the darts by; null shows them all together. */
  protected readonly groupKind = signal<GroupKind | null>(null);
  protected readonly groupName = computed(
    () => GROUP_KINDS.find((kind) => kind.value === this.groupKind())?.label ?? null,
  );
  /** The groupings to pick from, the current one ticked. */
  protected readonly groupItems = computed<MenuItem[]>(() => {
    const current = this.groupKind();
    const item = (label: string, kind: GroupKind | null): MenuItem => ({
      label,
      icon: kind === current ? 'pi pi-check' : 'pi pi-fw',
      command: () => this.groupBy(kind),
    });
    return [
      item($localize`:@@eval.group.off:Nicht gruppieren`, null),
      ...GROUP_KINDS.map((kind) => item(kind.label, kind.value)),
    ];
  });
  /** The groups of the current grouping, worded; null while nothing is grouped. */
  protected readonly chartGroups = computed<ChartGroup[] | null>(() => {
    const kind = this.groupKind();
    if (kind === null) {
      return null;
    }
    const rows = this.groups().find((group) => group.kind === kind)?.rows ?? [];
    return rows.map((row) => ({ ...row, label: groupLabel(kind, row.key) }));
  });
  protected readonly downloading = signal(false);
  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  private requests = 0;

  /** Tracker versions there are games of, newest first; null until they are known. */
  protected readonly versions = signal<number[] | null>(null);
  /** The known versions plus any the URL picked, so a pick always has its label. */
  protected readonly versionOptions = computed(() => {
    const picked = (this.filterValue().version ?? []).flatMap((v) => (v === null ? [] : [v]));
    return [...new Set<number>([...(this.versions() ?? []), ...picked])]
      .sort((a, b) => b - a)
      .map((version) => ({ label: `${version}`, value: version }));
  });
  protected readonly modeOptions = GAME_MODES.map((mode) => ({ label: `${mode}`, value: mode }));
  protected readonly runOptions = Object.entries(RUN_KIND_LABELS).map(([value, label]) => ({
    label,
    value: value as RunKind,
  }));

  protected readonly period = signal<Period>('all');
  protected readonly range = signal<DayRange>(null);

  protected readonly filters = this.fb.group({
    version: this.fb.control<[number | null, number | null] | null>(null),
    mode: this.fb.control<GameMode[]>([], { nonNullable: true }),
    run: this.fb.control<RunKind | null>(null),
    tilt: this.fb.control<[number, number] | null>(null),
  });
  protected readonly tiltLimits = TILT_LIMITS;
  /** The slider's range while it moves; applied once it rests. */
  protected readonly tiltDraft = signal<TiltRange>([...TILT_LIMITS]);
  /** A copy for the slider each time, since it moves its handles inside the array it gets. */
  protected readonly tiltModel = computed(() => [...this.tiltDraft()]);
  private tiltTimer: ReturnType<typeof setTimeout> | undefined;
  private readonly filterValue = toSignal(this.filters.valueChanges, {
    initialValue: this.filters.value,
  });
  private readonly queryState = new QueryState();

  /** The filters in use, as chips above the figures; the period shows in its own picker. */
  protected readonly chips = computed<FilterChip[]>(() => {
    const { version, mode, run, tilt } = this.filterValue();
    const period = this.period();
    const range = period === 'custom' ? dayRangeLabel(this.range(), this.locale) : null;
    const chips: FilterChip[] = [
      { key: 'period', label: range ?? PERIOD_CHIP_LABELS[period], removable: false, opens: true },
    ];
    const versions = version ? versionLabel(version) : null;
    if (versions) {
      chips.push({
        key: 'version',
        label: $localize`:@@eval.trackerChip:Tracker ${versions}:versions:`,
      });
    }
    const modes = this.chipLabel('mode', mode ?? []);
    if (modes) {
      chips.push({ key: 'mode', label: modes });
    }
    if (run) {
      chips.push({ key: 'run', label: RUN_KIND_LABELS[run] });
    }
    if (tilt) {
      chips.push({
        key: 'tilt',
        label: $localize`:@@eval.tiltChip:Neigung ${tilt[0]}:from:–${tilt[1]}:to:°`,
      });
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
    const { version, mode, run, tilt } = this.filterValue();
    if (version === null || version === undefined) {
      return null;
    }
    return {
      versionFrom: version[0],
      versionTo: version[1],
      modes: mode ?? [],
      testRun: run ? run === 'test' : null,
      ...periodBounds(this.period(), this.range(), new Date()),
      tiltFrom: tilt?.[0] ?? null,
      tiltTo: tilt?.[1] ?? null,
    };
  });

  constructor() {
    this.queryState.signal(
      'period',
      this.period,
      oneOfParam(PERIODS.days.map((option) => option.value)),
      'all',
    );
    this.queryState.signal('range', this.range, DAY_RANGE_PARAM, null);
    this.queryState.signal(
      'group',
      this.groupKind,
      oneOfParam(GROUP_KINDS.map((kind) => kind.value)) as QueryParam<GroupKind | null>,
      null,
    );
    this.queryState.signal('tab', this.tab, oneOfParam(TABS), 'overview');
    this.queryState.form(this.filters, FILTER_PARAMS);
    this.tiltDraft.set([...(this.filters.controls.tilt.value ?? TILT_LIMITS)]);
    this.filters.controls.tilt.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((tilt) => this.tiltDraft.set([...(tilt ?? TILT_LIMITS)]));
    this.destroyRef.onDestroy(() => clearTimeout(this.tiltTimer));
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

  /** Groups the analysis and shows it, since only the analysis is split. */
  protected groupBy(kind: GroupKind | null): void {
    this.groupKind.set(kind);
    if (kind !== null) {
      this.tab.set('analysis');
    }
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
      this.filters.controls.version.setValue([null, null]);
    } else {
      this.filters.get(key)?.reset();
    }
  }

  /** One end of the version range; the other keeps its pick. */
  protected setVersion(end: 0 | 1, version: number | null): void {
    const range: [number | null, number | null] = [
      ...(this.filters.controls.version.value ?? [null, null]),
    ];
    range[end] = version;
    this.filters.controls.version.setValue(range);
  }

  /** Follows the slider and applies its range once it rests; the full span narrows nothing. */
  protected slideTilt(range: readonly number[]): void {
    const [from, to] = range;
    this.tiltDraft.set([from, to]);
    clearTimeout(this.tiltTimer);
    this.tiltTimer = setTimeout(() => {
      const full = from <= TILT_LIMITS[0] && to >= TILT_LIMITS[1];
      this.filters.controls.tilt.setValue(full ? null : [from, to]);
    }, TILT_DEBOUNCE_MS);
  }

  /** The selection as a Markdown report; a failure shows as the interceptor's toast. */
  protected async download(): Promise<void> {
    const criteria = this.criteria();
    if (!criteria || this.downloading()) {
      return;
    }
    this.downloading.set(true);
    try {
      await this.evaluation.downloadReport(criteria);
    } catch {
      // Already reported by the error interceptor.
    } finally {
      this.downloading.set(false);
    }
  }

  /** One game's figures on their own page; going back returns to this tab and filters. */
  protected openGame(gameId: string): void {
    void this.router.navigate(['/account/evaluation', gameId], {
      state: backState($localize`:@@auth.account.evaluation:Auswertung`),
    });
  }

  protected retry(): void {
    const criteria = this.criteria();
    if (criteria) {
      void this.load(criteria);
    } else {
      void this.loadVersions();
    }
  }

  private newest(): [number | null, number | null] {
    const newest = this.versions()?.[0] ?? null;
    return [newest, newest];
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
        this.groups.set(report.groups);
        this.failures.set(report.failures);
        this.mismatches.set(report.mismatches);
        this.tips.set(report.tips);
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
