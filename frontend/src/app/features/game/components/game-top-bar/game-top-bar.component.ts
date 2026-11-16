import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { Button } from 'primeng/button';
import { AnnouncerToggleComponent } from '../../../announcement/components/announcer-toggle/announcer-toggle.component';
import { TorchToggleComponent } from '../../../camera/components/torch-toggle/torch-toggle.component';
import { ShareDialogComponent } from '../../../../core/view/components/share-dialog/share-dialog.component';
import { ConfirmService } from '../../../../core/view/services/confirm.service';
import { playOf } from '../../models/game-settings';
import { variantLabel } from '../../models/game-variant';
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
    ShareDialogComponent,
  ],
  templateUrl: './game-top-bar.component.html',
  styleUrl: './game-top-bar.component.scss',
  // Scoped to this component so its <p-confirmdialog> shares the same instance.
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameTopBarComponent {
  protected readonly game = inject(GameService);

  private readonly document = inject(DOCUMENT);
  private readonly session = inject(GameSessionService);
  private readonly confirm = inject(ConfirmService);

  protected readonly shareDialogVisible = signal(false);

  /** Milliseconds since the epoch, ticking each second while a timed training runs. */
  private readonly now = signal(Date.now());

  /** The time a timed training has left, from the last state and when it came in. */
  private readonly timer = computed(() => {
    const state = this.game.state();
    if (state === null || state.ended || state.settings.variant !== 'training' || state.settings.minutes === null) {
      return null;
    }
    const play = playOf(state);
    const left = play.variant === 'training' ? play.standing.secondsLeft : null;
    return { minutes: state.settings.minutes, left, receivedAt: Date.now() };
  });

  /** How far a training set to darts or minutes is: "37 / 90", "12:34", or the last round. */
  protected readonly limit = computed(() => {
    const state = this.game.state();
    if (state === null || state.ended || state.settings.variant !== 'training') {
      return null;
    }
    if (state.settings.darts !== null) {
      const play = playOf(state);
      const own = play.variant === 'training' ? play.standing.players[state.currentPlayerIndex] : undefined;
      return `${own?.darts ?? 0} / ${state.settings.darts}`;
    }
    const timer = this.timer();
    if (timer === null) {
      return null;
    }
    const seconds =
      timer.left === null ? timer.minutes * 60 : timer.left - (this.now() - timer.receivedAt) / 1000;
    if (seconds <= 0) {
      return $localize`:@@game.training.lastRound:Letzte Runde`;
    }
    const whole = Math.ceil(seconds);
    return `${Math.floor(whole / 60)}:${`${whole % 60}`.padStart(2, '0')}`;
  });

  constructor() {
    effect((onCleanup) => {
      if (this.timer()?.left == null) {
        return;
      }
      const id = setInterval(() => this.now.set(Date.now()), 1000);
      onCleanup(() => clearInterval(id));
    });
  }

  /** The mode alone names an x01 game; elimination shares those numbers as its
   * target and has to say so, and the other variants go by their name. */
  protected readonly title = computed(() => {
    const state = this.game.state();
    if (state === null) {
      return '';
    }
    const settings = state.settings;
    if (settings.variant === 'x01') {
      return `${settings.mode}`;
    }
    const name = variantLabel(settings.variant);
    return settings.variant === 'elimination' ? `${name} ${settings.mode}` : name;
  });

  /** The link a second device follows to join, built from this page's origin. */
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
    if (this.game.finished()) {
      this.leaveGame();
      return;
    }
    this.confirm.ask(
      $localize`:@@game.leave:Spiel verlassen`,
      $localize`:@@game.leaveText:Spiel auf diesem Gerät verlassen? Der bisherige Spielstand bleibt gespeichert.`,
      $localize`:@@game.leaveAction:Verlassen`,
      () => this.leaveGame(),
    );
  }

  /** A training has no winner to end it, so this does, after asking. */
  protected confirmEndTraining(): void {
    this.confirm.ask(
      $localize`:@@game.endTraining:Training beenden`,
      $localize`:@@game.endTrainingText:Training beenden? Du kannst danach noch zurück ins Training.`,
      $localize`:@@game.endTrainingAction:Beenden`,
      () => this.game.setEnded(true),
      true,
    );
  }

  private leaveGame(): void {
    this.session.leave();
  }
}
