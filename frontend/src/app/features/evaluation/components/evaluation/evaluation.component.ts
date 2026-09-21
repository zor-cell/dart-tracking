import { DatePipe, DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { ProgressSpinner } from 'primeng/progressspinner';
import { Select } from 'primeng/select';
import { AccuracySummaryDto, GameAccuracyDto } from '../../dto/accuracy.dto';
import { EvaluationService } from '../../services/evaluation.service';

/** What the outcome counts are called on the page, in reading order. */
const OUTCOMES: readonly { key: keyof AccuracySummaryDto; label: string; hint: string }[] = [
  { key: 'correct', label: 'Korrekt', hint: 'Im richtigen Segment gebucht' },
  { key: 'wrong', label: 'Falsch', hint: 'Gebucht, aber im falschen Segment' },
  { key: 'missed', label: 'Verpasst', hint: 'Geworfen, von der Kamera nie gebucht' },
  { key: 'phantom', label: 'Phantom', hint: 'Gebucht, ohne dass ein Pfeil steckte' },
];

interface ScopeOption {
  readonly gameId: string | null;
  readonly label: string;
}

@Component({
  selector: 'app-evaluation',
  imports: [
    Button,
    DecimalPipe,
    FormsModule,
    NgTemplateOutlet,
    ProgressSpinner,
    RouterLink,
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

  protected share(count: number): number | null {
    const summary = this.summary();
    if (!summary) {
      return null;
    }
    const judged = summary.correct + summary.wrong + summary.missed + summary.phantom;
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
