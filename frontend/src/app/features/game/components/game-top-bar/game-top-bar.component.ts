import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { Button } from 'primeng/button';
import { NotificationService } from '../../../../core/notification/services/notification.service';
import { GameService } from '../../services/game.service';
import { GameSessionService } from '../../services/game-session.service';

/**
 * Chrome shown at the top of the shell while a game is active (gated on
 * `game.state()` in the app shell). Holds game-scoped actions that do not belong
 * to the scoreboard itself — ending the game, and later sharing it so another
 * device can follow along. Per-turn actions (undo, recalibrate) stay in the game
 * view where they are used.
 */
@Component({
  selector: 'app-game-top-bar',
  imports: [Button],
  templateUrl: './game-top-bar.component.html',
  styleUrl: './game-top-bar.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameTopBarComponent {
  protected readonly game = inject(GameService);

  private readonly session = inject(GameSessionService);
  private readonly notification = inject(NotificationService);
  private readonly router = inject(Router);

  /** Share the running game so a second device can join via QR and watch the
   * live state. Placeholder until the backend broadcasts to multiple viewers. */
  protected share(): void {
    this.notification.showInfo('Teilen kommt bald.');
  }

  /** End the game entirely: tear down the live session and clear the state. */
  protected endGame(): void {
    this.session.endSession();
    this.game.reset();
    void this.router.navigate(['/start']);
  }
}
