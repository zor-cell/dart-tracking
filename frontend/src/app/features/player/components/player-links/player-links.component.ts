import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Button } from 'primeng/button';
import { Dialog } from 'primeng/dialog';
import { PlayerLinkDto } from '../../dto/player-link.dto';
import { PlayerService } from '../../services/player.service';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';

/** The players in other people's lists that are linked to this account, and the
 * retired ones that only hold past games, each with a way to undo the link. */
@Component({
  selector: 'app-player-links',
  imports: [Button, Dialog, EmptyStateComponent, LoadErrorComponent, LoadingStateComponent],
  templateUrl: './player-links.component.html',
  styleUrl: './player-links.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlayerLinksComponent {
  private readonly players = inject(PlayerService);

  protected readonly links = signal<PlayerLinkDto[]>([]);
  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  protected readonly active = computed(() => this.links().filter((link) => !link.retired));
  protected readonly retired = computed(() => this.links().filter((link) => link.retired));
  protected readonly leaving = signal<PlayerLinkDto | null>(null);
  protected readonly dialogOpen = signal(false);
  protected readonly busy = signal(false);

  constructor() {
    void this.load();
  }

  protected async load(): Promise<void> {
    this.failed.set(false);
    try {
      this.links.set(await this.players.links());
    } catch {
      this.failed.set(true);
    } finally {
      this.loading.set(false);
    }
  }

  protected ask(link: PlayerLinkDto): void {
    this.leaving.set(link);
    this.dialogOpen.set(true);
  }

  protected async leave(keepHistory: boolean): Promise<void> {
    const link = this.leaving();
    if (link === null || this.busy()) {
      return;
    }
    this.busy.set(true);
    try {
      await this.players.leave(link.playerId, keepHistory);
      this.dialogOpen.set(false);
      // Keeping the history turns the link into a retired one.
      await this.load();
    } catch {
      // The error banner already says what went wrong.
    } finally {
      this.busy.set(false);
    }
  }
}
