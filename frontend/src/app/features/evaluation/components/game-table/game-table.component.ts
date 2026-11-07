import { DatePipe, DecimalPipe, formatDate } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  LOCALE_ID,
  computed,
  inject,
  input,
  output,
} from '@angular/core';
import { TableModule } from 'primeng/table';
import { GameAccuracyDto } from '../../dto/accuracy.dto';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { PAGE_SIZE } from '../../../../core/view/models/page-size';
import { SHORT_DATE, SHORT_DATE_TIME } from '../../../../core/i18n/models/date-format';

/** Every evaluated game with its hit rate, newest first; a row opens the game's figures. */
@Component({
  selector: 'app-game-table',
  imports: [DatePipe, DecimalPipe, EmptyStateComponent, TableModule],
  templateUrl: './game-table.component.html',
  styleUrl: './game-table.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameTableComponent {
  private readonly locale = inject(LOCALE_ID);

  readonly games = input.required<readonly GameAccuracyDto[]>();
  readonly gameOpen = output<string>();

  protected readonly pageSize = PAGE_SIZE;
  protected readonly shortDate = SHORT_DATE;
  protected readonly pageReport = $localize`:@@common.pageReport:{first}–{last} von {totalRecords}`;

  protected readonly rows = computed(() =>
    this.games().map((game) => ({
      ...game,
      versions: game.trackerVersions.join(', ') || '–',
      rate: game.summary.dartsThrown === 0 ? null : game.summary.correct / game.summary.dartsThrown,
    })),
  );

  protected openLabel(game: GameAccuracyDto): string {
    const when = formatDate(game.createdAt, SHORT_DATE_TIME, this.locale);
    return $localize`:@@game.list.open:Spiel vom ${when}:date: öffnen`;
  }
}
