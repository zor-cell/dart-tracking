import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { QRCodeComponent } from 'angularx-qrcode';
import { ConfirmationService } from 'primeng/api';
import { Button } from 'primeng/button';
import { ConfirmDialog } from 'primeng/confirmdialog';
import { Dialog } from 'primeng/dialog';
import { NotificationService } from '../../../../core/notification/services/notification.service';
import { GameService } from '../../services/game.service';
import { GameSessionService } from '../../services/game-session.service';

/**
 * Chrome shown at the top of the shell while a game is active (gated on
 * `game.state()` in the app shell). Holds game-scoped actions that do not belong
 * to the scoreboard itself — sharing the game and leaving it. Per-turn actions
 * (undo, recalibrate) stay in the game view where they are used.
 */
@Component({
  selector: 'app-game-top-bar',
  imports: [Button, ConfirmDialog, Dialog, QRCodeComponent],
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
  private readonly notification = inject(NotificationService);
  private readonly confirmation = inject(ConfirmationService);
  private readonly router = inject(Router);

  protected readonly shareDialogVisible = signal(false);

  /**
   * The link a second device follows to join. Built from the origin this device
   * loaded the app from, which is what makes it reachable for the other phone:
   * on a LAN that is the host's address, not `localhost`.
   */
  protected readonly shareUrl = computed(() => {
    const id = this.game.state()?.id;
    return id ? `${this.document.location.origin}/game/join/${id}` : '';
  });

  /** Web Share is the nicest hand-off where it exists (secure contexts only), so
   * the button appears only when the browser actually has it. */
  protected readonly canShareNatively = Boolean(this.window?.navigator.share);

  private get window(): (Window & typeof globalThis) | null {
    return this.document.defaultView;
  }

  protected openShareDialog(): void {
    this.shareDialogVisible.set(true);
  }

  /** Hand the link to the OS share sheet. A cancelled sheet rejects, which is
   * not a failure worth reporting. */
  protected async shareNatively(): Promise<void> {
    try {
      await this.window?.navigator.share({ title: 'Dart-Spiel', url: this.shareUrl() });
    } catch {
      // dismissed by the user
    }
  }

  /**
   * Copy the link. The Clipboard API needs a secure context, which the dev setup
   * over plain HTTP on a LAN address is not — so a failure is expected there and
   * says what to do instead, rather than reading as a bug.
   */
  protected async copyLink(): Promise<void> {
    try {
      await this.window?.navigator.clipboard.writeText(this.shareUrl());
      this.notification.showSuccess('Link kopiert.');
    } catch {
      this.notification.showWarning('Kopieren nicht möglich — bitte den QR-Code scannen.');
    }
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
