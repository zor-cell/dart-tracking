import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { GameReportDto } from '../../dto/accuracy.dto';
import { RUN_KIND_LABELS } from '../../models/evaluation-filter';
import { EvaluationService } from '../../services/evaluation.service';
import { AccuracyChartsComponent } from '../accuracy-charts/accuracy-charts.component';
import { AccuracySummaryComponent } from '../accuracy-summary/accuracy-summary.component';
import { MismatchTableComponent } from '../mismatch-table/mismatch-table.component';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { SHORT_DATE_TIME } from '../../../../core/i18n/models/date-format';

/** How well the tracker scored in one game, opened from the evaluation's game list or chart. */
@Component({
  selector: 'app-evaluation-game',
  imports: [
    AccuracyChartsComponent,
    AccuracySummaryComponent,
    BackLinkComponent,
    DatePipe,
    LoadErrorComponent,
    LoadingStateComponent,
    MismatchTableComponent,
  ],
  templateUrl: './evaluation-game.component.html',
  styleUrl: './evaluation-game.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EvaluationGameComponent {
  private readonly evaluation = inject(EvaluationService);
  private readonly route = inject(ActivatedRoute);

  protected readonly report = signal<GameReportDto | null>(null);
  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  protected readonly shortDateTime = SHORT_DATE_TIME;
  protected readonly testRun = RUN_KIND_LABELS.test;

  constructor() {
    void this.load();
  }

  protected async load(): Promise<void> {
    this.loading.set(true);
    this.failed.set(false);
    try {
      this.report.set(await this.evaluation.loadGame(this.route.snapshot.paramMap.get('gameId') ?? ''));
    } catch {
      this.failed.set(true);
    } finally {
      this.loading.set(false);
    }
  }
}
