import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { KillStatisticsDto } from '../../dto/kill-statistics.dto';
import { Comparison } from '../../models/comparison';
import { ComparedValueComponent } from '../compared-value/compared-value.component';
import { DeltaMarkComponent } from '../delta-mark/delta-mark.component';
import { StatLinkComponent } from '../stat-link/stat-link.component';

/** Kills in Elimination or Killer: how many, per game, against what was taken from oneself. */
@Component({
  selector: 'app-kill-statistics',
  imports: [ComparedValueComponent, DecimalPipe, DeltaMarkComponent, InfoHintComponent, StatLinkComponent],
  templateUrl: './kill-statistics.component.html',
  styleUrl: './kill-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KillStatisticsComponent {
  readonly statistics = input.required<KillStatisticsDto>();
  readonly comparison = input<Comparison<KillStatisticsDto> | null>(null);
  /** Killer counts lives, Elimination resets. */
  readonly killer = input(false);

  protected readonly perGame = computed(() => perGame(this.statistics()));
  protected readonly otherPerGame = computed(() => {
    const other = this.comparison()?.statistics;
    return other ? perGame(other) : null;
  });
}

function perGame({ kills, games }: KillStatisticsDto): number | null {
  return games.length === 0 ? null : kills / games.length;
}
