import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { KillStatisticsDto } from '../../dto/kill-statistics.dto';
import { StatLinkComponent } from '../stat-link/stat-link.component';

/** Kills in Elimination or Killer: how many, per game, against what was taken from oneself. */
@Component({
  selector: 'app-kill-statistics',
  imports: [DecimalPipe, InfoHintComponent, StatLinkComponent],
  templateUrl: './kill-statistics.component.html',
  styleUrl: './kill-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KillStatisticsComponent {
  readonly statistics = input.required<KillStatisticsDto>();
  /** Killer counts lives, Elimination resets. */
  readonly killer = input(false);

  protected readonly perGame = computed(() => {
    const { kills, games } = this.statistics();
    return games.length === 0 ? null : kills / games.length;
  });
}
