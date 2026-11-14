import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { backState } from '../../../../core/view/models/back-state';
import { KillStatisticsDto } from '../../dto/kill-statistics.dto';

/** Kills in Elimination or Killer: how many, per game, against what was taken from oneself. */
@Component({
  selector: 'app-kill-statistics',
  imports: [DecimalPipe, InfoHintComponent, RouterLink],
  templateUrl: './kill-statistics.component.html',
  styleUrl: './kill-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KillStatisticsComponent {
  readonly statistics = input.required<KillStatisticsDto>();
  /** Killer counts lives, Elimination resets. */
  readonly killer = input(false);

  protected readonly returnState = backState($localize`:@@auth.account.stats:Statistik`);

  protected readonly perGame = computed(() => {
    const { kills, games } = this.statistics();
    return games.length === 0 ? null : kills / games.length;
  });
}
