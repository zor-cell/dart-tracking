import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Params, RouterLink } from '@angular/router';
import { backState } from '../../../../core/view/models/back-state';

/** Where a figure's link leads: the visit in its replay, the game, or the list of games. */
export type StatLinkAction = 'replay' | 'game' | 'games';

const ACTION_LABELS: Record<StatLinkAction, string> = {
  replay: $localize`:@@stats.openReplay:, im Replay öffnen`,
  game: $localize`:@@stats.targets.openGame:, Spiel öffnen`,
  games: $localize`:@@stats.showGames:, Spiele zeigen`,
};

/** A figure of a statistics card as a link to where it was thrown. */
@Component({
  selector: 'app-stat-link',
  imports: [RouterLink],
  templateUrl: './stat-link.component.html',
  styleUrl: './stat-link.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatLinkComponent {
  readonly link = input.required<string | readonly unknown[]>();
  readonly queryParams = input<Params | null>(null);
  readonly action = input<StatLinkAction>('replay');

  /** Brings the opened view back here. */
  protected readonly returnState = backState($localize`:@@auth.account.stats:Statistik`);
  protected readonly actionLabel = computed(() => ACTION_LABELS[this.action()]);
}
