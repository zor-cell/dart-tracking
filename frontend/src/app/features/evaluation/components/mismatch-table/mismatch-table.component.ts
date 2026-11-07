import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TableModule } from 'primeng/table';
import { Tag } from 'primeng/tag';
import { DartOutcome, GameAccuracyDto, MismatchDto } from '../../dto/accuracy.dto';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { PAGE_SIZE } from '../../../../core/view/models/page-size';
import { SHORT_DATE } from '../../../../core/i18n/models/date-format';

const OUTCOME_TAGS: Record<DartOutcome, { label: string; severity: 'danger' | 'warn' | 'secondary' | 'success' }> = {
  correct: { label: $localize`:@@eval.correct:Korrekt`, severity: 'success' },
  wrong: { label: $localize`:@@eval.wrong:Falsch`, severity: 'danger' },
  missed: { label: $localize`:@@eval.missed:Verpasst`, severity: 'warn' },
  phantom: { label: $localize`:@@eval.phantom:Phantom`, severity: 'secondary' },
};

/** Every dart the tracker got wrong, nearest to its segment first, paged on the page. */
@Component({
  selector: 'app-mismatch-table',
  imports: [DatePipe, DecimalPipe, EmptyStateComponent, TableModule, Tag],
  templateUrl: './mismatch-table.component.html',
  styleUrl: './mismatch-table.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MismatchTableComponent {
  readonly mismatches = input.required<readonly MismatchDto[]>();
  /** The games the mismatches come from, to date each one. */
  readonly games = input.required<readonly GameAccuracyDto[]>();

  protected readonly pageSize = PAGE_SIZE;
  protected readonly shortDate = SHORT_DATE;
  protected readonly pageReport = $localize`:@@common.pageReport:{first}–{last} von {totalRecords}`;

  private readonly playedAt = computed(
    () => new Map(this.games().map((game) => [game.gameId, game.createdAt])),
  );

  protected readonly rows = computed(() =>
    this.mismatches().map((mismatch, index) => ({
      ...mismatch,
      index,
      tag: OUTCOME_TAGS[mismatch.outcome],
      playedAt: this.playedAt().get(mismatch.gameId) ?? null,
    })),
  );

  protected readonly throwLabel = (turn: number, dart: number): string =>
    $localize`:@@eval.mismatch.throw:Visit ${turn + 1}:turn:, #${dart}:dart:`;
}
