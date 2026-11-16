import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { Button } from 'primeng/button';
import { AnnouncerToggleComponent } from '../../../announcement/components/announcer-toggle/announcer-toggle.component';
import { TorchToggleComponent } from '../../../camera/components/torch-toggle/torch-toggle.component';
import { ShareDialogComponent } from '../../../../core/view/components/share-dialog/share-dialog.component';
import { ConfirmService } from '../../../../core/view/services/confirm.service';
import { playOf } from '../../models/game-settings';
import { ProgressSegment } from '../../models/progress-segment';
import { variantLabel } from '../../models/game-variant';
import { GameService } from '../../services/game.service';
import { GameSessionService } from '../../services/game-session.service';
import { ProgressSegmentsComponent } from '../progress-segments/progress-segments.component';

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
    ProgressSegmentsComponent,
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

  /** Seconds a timed training has left, counting down between states; null without a time. */
  private readonly secondsLeft = computed(() => {
    const timer = this.timer();
    if (timer === null) {
      return null;
    }
    return timer.left === null ? timer.minutes * 60 : timer.left - (this.now() - timer.receivedAt) / 1000;
  });

  /** Darts the current player threw in a training set to darts, with the limit. */
  private readonly dartsLimit = computed(() => {
    const state = this.game.state();
    if (state === null || state.ended || state.settings.variant !== 'training' || state.settings.darts === null) {
      return null;
    }
    const play = playOf(state);
    const own = play.variant === 'training' ? play.standing.players[state.currentPlayerIndex] : undefined;
    return { thrown: own?.darts ?? 0, limit: state.settings.darts };
  });

  /** The time a timed training has left, "12:34", or the last round. */
  protected readonly limit = computed(() => {
    const seconds = this.secondsLeft();
    if (seconds === null) {
      return null;
    }
    if (seconds <= 0) {
      return $localize`:@@game.training.lastRound:Letzte Runde`;
    }
    const whole = Math.ceil(seconds);
    return `${Math.floor(whole / 60)}:${`${whole % 60}`.padStart(2, '0')}`;
  });

  /** The strip under the bar: a personal plan's blocks, or a training's darts or time used. */
  protected readonly progress = computed<readonly ProgressSegment[] | null>(() => {
    const state = this.game.state();
    if (state === null) {
      return null;
    }
    const play = playOf(state);
    if (play.variant === 'personal') {
      const own = play.standing.players[state.currentPlayerIndex];
      const blocks = play.standing.blocks;
      let before = 0;
      return blocks.map((block, index) => {
        const thrown = Math.min(Math.max((own?.darts ?? 0) - before, 0), block.darts);
        before += block.darts;
        return {
          value: (100 * thrown) / block.darts,
          weight: block.darts,
          label: $localize`:@@game.progress.block:Block ${index + 1}:index: von ${blocks.length}:count:`,
        };
      });
    }
    const label = $localize`:@@game.progress.training:Fortschritt des Trainings`;
    const darts = this.dartsLimit();
    if (darts !== null) {
      return [{ value: Math.min((100 * darts.thrown) / darts.limit, 100), weight: 1, label }];
    }
    const seconds = this.secondsLeft();
    const minutes = this.timer()?.minutes;
    if (seconds === null || minutes === undefined) {
      return null;
    }
    return [{ value: Math.min(Math.max(100 - seconds / (minutes * 0.6), 0), 100), weight: 1, label }];
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
