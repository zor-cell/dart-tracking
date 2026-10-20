import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { QRCodeComponent } from 'angularx-qrcode';
import { ConfirmationService } from 'primeng/api';
import { Button } from 'primeng/button';
import { ConfirmDialog } from 'primeng/confirmdialog';
import { Dialog } from 'primeng/dialog';
import { Divider } from 'primeng/divider';
import { InputText } from 'primeng/inputtext';
import { AnnouncerToggleComponent } from '../../../announcement/components/announcer-toggle/announcer-toggle.component';
import { TorchToggleComponent } from '../../../camera/components/torch-toggle/torch-toggle.component';
import { NotificationService } from '../../../../core/notification/services/notification.service';
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
    Dialog,
    Divider,
    InputText,
    QRCodeComponent,
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
  private readonly notification = inject(NotificationService);
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

  private get window(): (Window & typeof globalThis) | null {
    return this.document.defaultView;
  }

  protected openShareDialog(): void {
    this.shareDialogVisible.set(true);
  }

  /** Select the whole link on focus, so copying by hand is one keystroke away. */
  protected selectLink(event: Event): void {
    (event.target as HTMLInputElement).select();
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
