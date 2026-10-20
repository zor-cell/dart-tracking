import { DatePipe, DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Select } from 'primeng/select';
import { AccuracySummaryDto, FieldKind, GameAccuracyDto } from '../../dto/accuracy.dto';
import { EvaluationService } from '../../services/evaluation.service';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';

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
    LoadingStateComponent,
    NgTemplateOutlet,
    EmptyStateComponent,
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

  protected readonly total = signal<AccuracySummaryDto | null>(null);
  protected readonly games = signal<readonly GameAccuracyDto[]>([]);
  protected readonly selectedGameId = signal<string | null>(null);
  protected readonly loading = signal(true);

  protected readonly outcomes = OUTCOMES;
  protected readonly fieldLabels = FIELD_LABELS;

  /** The whole set first, then one entry per logged game, newest first. */
  protected readonly scopes = computed<ScopeOption[]>(() => [
    { gameId: null, label: `Gesamt (${this.games().length} Spiele)` },
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
    void this.reload();
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

  private labelOf(game: GameAccuracyDto): string {
    const date = this.dates.transform(game.createdAt, 'dd.MM.yy HH:mm') ?? '';
    const marker = game.evaluationEnabled ? ' · Testlauf' : '';
    return `${date} · ${game.mode}${marker}`;
  }

  private async reload(): Promise<void> {
    this.loading.set(true);
    try {
      const report = await this.evaluation.loadAccuracy();
      this.total.set(report.total);
      this.games.set(report.games);
    } finally {
      this.loading.set(false);
    }
  }
}
