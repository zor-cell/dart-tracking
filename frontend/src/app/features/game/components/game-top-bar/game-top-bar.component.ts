import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { ConfirmationService } from 'primeng/api';
import { Button } from 'primeng/button';
import { ConfirmDialog } from 'primeng/confirmdialog';
import { NotificationService } from '../../../../core/notification/services/notification.service';
import { GameService } from '../../services/game.service';
import { GameSessionService } from '../../services/game-session.service';

/**
 * Chrome shown at the top of the shell while a game is active (gated on
 * `game.state()` in the app shell). Holds game-scoped actions that do not belong
 * to the scoreboard itself — leaving the game, and later sharing it. Per-turn
 * actions (undo, recalibrate) stay in the game view where they are used.
 */
@Component({
  selector: 'app-game-top-bar',
  imports: [Button, ConfirmDialog],
  templateUrl: './game-top-bar.component.html',
  styleUrl: './game-top-bar.component.scss',
  // Scoped to this component so its <p-confirmdialog> shares the same instance.
  providers: [ConfirmationService],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameTopBarComponent {
  protected readonly game = inject(GameService);

  private readonly session = inject(GameSessionService);
  private readonly notification = inject(NotificationService);
  private readonly confirmation = inject(ConfirmationService);
  private readonly router = inject(Router);

  /** Placeholder until sharing a game across devices is built. */
  protected share(): void {
    this.notification.showInfo('Teilen kommt bald.');
  }

  /** Ending the game tears down the running session and cannot be undone, so
   * confirm it in a modal dialog before acting. */
  protected confirmEndGame(): void {
    this.confirmation.confirm({
      header: 'Spiel beenden',
      message: 'Spiel wirklich beenden? Die Daten gehen dann verloren.',
      icon: 'pi pi-exclamation-triangle',
      rejectButtonProps: { label: 'Abbrechen', severity: 'secondary', text: true },
      acceptButtonProps: { label: 'Beenden', severity: 'danger' },
      accept: () => this.endGame(),
    });
  }

  /** End the game entirely: tear down the live session and clear the state. */
  private endGame(): void {
    this.session.endSession();
    this.game.reset();
    void this.router.navigate(['/start']);
  }
}
