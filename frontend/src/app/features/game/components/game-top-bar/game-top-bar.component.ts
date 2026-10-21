import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ConfirmationService } from 'primeng/api';
import { Button } from 'primeng/button';
import { ConfirmDialog } from 'primeng/confirmdialog';
import { AnnouncerToggleComponent } from '../../../announcement/components/announcer-toggle/announcer-toggle.component';
import { TorchToggleComponent } from '../../../camera/components/torch-toggle/torch-toggle.component';
import { ShareDialogComponent } from '../../../../core/view/components/share-dialog/share-dialog.component';
import { GameService } from '../../services/game.service';
import { GameSessionService } from '../../services/game-session.service';

/**
 * Header of the game view, holding the game-scoped actions that do not belong to
 * the scoreboard itself — sharing the game and leaving it. Per-turn actions
 * (undo, recalibrate) stay in the view below, where they are used.
 */
@Component({
  selector: 'app-game-top-bar',
  imports: [
    AnnouncerToggleComponent,
    TorchToggleComponent,
    Button,
    ConfirmDialog,
    ShareDialogComponent,
  ],
  templateUrl: './game-top-bar.component.html',
  styleUrl: './game-top-bar.component.scss',
  // Scoped to this component so its <p-confirmdialog> shares the same instance.
  providers: [ConfirmationService],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameTopBarComponent {
  protected readonly game = inject(GameService);

  private readonly document = inject(DOCUMENT);
  private readonly session = inject(GameSessionService);
  private readonly confirmation = inject(ConfirmationService);

  protected readonly shareDialogVisible = signal(false);

  /** The mode alone names an x01 game; elimination shares those numbers as its
   * target and has to say so. */
  protected readonly title = computed(() => {
    const state = this.game.state();
    if (state === null) {
      return '';
    }
    return state.variant === 'elimination' ? `Elimination ${state.mode}` : `${state.mode}`;
  });

  /**
   * The link a second device follows to join. Built from the origin this device
   * loaded the app from, which is what makes it reachable for the other phone:
   * on a LAN that is the host's address, not `localhost`.
   */
  protected readonly shareUrl = computed(() => {
    const id = this.game.state()?.id;
    return id ? `${this.document.location.origin}/game/join/${id}` : '';
  });

  protected openShareDialog(): void {
    this.shareDialogVisible.set(true);
  }

  /** Leaving a running game stops this device's part in it, so that asks first;
   * a finished one is left at once. */
  protected confirmLeaveGame(): void {
    if (this.game.settledWinner() !== null) {
      this.leaveGame();
      return;
    }
    this.confirmation.confirm({
      header: 'Spiel verlassen',
      message: 'Spiel auf diesem Gerät verlassen? Der bisherige Spielstand bleibt gespeichert.',
      icon: 'pi pi-exclamation-triangle',
      rejectButtonProps: { label: 'Abbrechen', severity: 'secondary', text: true },
      acceptButtonProps: { label: 'Verlassen', severity: 'danger' },
      accept: () => this.leaveGame(),
    });
  }

  private leaveGame(): void {
    this.session.leave();
  }
}
