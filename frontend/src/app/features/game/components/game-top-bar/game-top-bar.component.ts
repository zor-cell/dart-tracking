import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { Button } from 'primeng/button';
import { AnnouncerToggleComponent } from '../../../announcement/components/announcer-toggle/announcer-toggle.component';
import { TorchToggleComponent } from '../../../camera/components/torch-toggle/torch-toggle.component';
import { ShareDialogComponent } from '../../../../core/view/components/share-dialog/share-dialog.component';
import { ConfirmService } from '../../../../core/view/services/confirm.service';
import { playOf } from '../../models/game-settings';
import { blockSeconds } from '../../models/personal-blocks';
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
  protected readonly leaveLabel = $localize`:@@game.leave:Spiel verlassen`;
  protected readonly endTrainingLabel = $localize`:@@game.endTraining:Training beenden`;

  /** A running free training has no winner, so closing it ends it rather than leaving. */
  protected readonly endsTraining = computed(() => {
    const state = this.game.state();
    return state !== null && state.settings.variant === 'training' && !this.game.finished();
  });

  /** Milliseconds since the epoch, ticking each second while a timed training runs. */
  private readonly now = signal(Date.now());

  /** The time a timed training or personal plan has left, from the last state and when it came in. */
  private readonly timer = computed(() => {
    const state = this.game.state();
    if (state === null || state.ended) {
      return null;
    }
    const play = playOf(state);
    if ((play.variant !== 'training' && play.variant !== 'personal') || play.settings.minutes === null) {
      return null;
    }
    return { minutes: play.settings.minutes, left: play.standing.secondsLeft, receivedAt: Date.now() };
  });

  /** Seconds a timed training has left, counting down between states; null without a time. */
  private readonly secondsLeft = computed(() => {
    const timer = this.timer();
    if (timer === null) {
      return null;
    }
    // The clock may still read a time before the state came in; that counts as no time passed.
    const elapsed = Math.max(this.now() - timer.receivedAt, 0) / 1000;
    return timer.left === null ? timer.minutes * 60 : timer.left - elapsed;
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

  /** What stands under the strip: the time left, "12:34", or the darts thrown, "37 / 90". */
  protected readonly progressLabel = computed(() => {
    const seconds = this.secondsLeft();
    if (seconds !== null) {
      const whole = Math.ceil(Math.max(seconds, 0));
      return `${Math.floor(whole / 60)}:${`${whole % 60}`.padStart(2, '0')}`;
    }
    const darts = this.dartsLimit();
    if (darts !== null) {
      return `${darts.thrown} / ${darts.limit}`;
    }
    const state = this.game.state();
    const play = state === null ? null : playOf(state);
    if (play?.variant !== 'personal' || state === null || state.ended) {
      return null;
    }
    const planned = play.standing.blocks.reduce((sum, block) => sum + block.darts, 0);
    return `${play.standing.players[state.currentPlayerIndex]?.darts ?? 0} / ${planned}`;
  });

  /** The strip under the bar: a personal plan's blocks, or a training's darts or time used. */
  protected readonly progress = computed<readonly ProgressSegment[] | null>(() => {
    const state = this.game.state();
    if (state === null) {
      return null;
    }
    const play = playOf(state);
    if (play.variant === 'personal') {
      const blocks = play.standing.blocks;
      const minutes = play.settings.minutes;
      // Each block fills by its darts, or by its share of the time when the plan is timed.
      const sizes = minutes === null ? blocks.map((block) => block.darts) : blockSeconds(blocks, minutes);
      const seconds = this.secondsLeft();
      let done =
        minutes === null
          ? (play.standing.players[state.currentPlayerIndex]?.darts ?? 0)
          : state.ended
            ? minutes * 60
            : minutes * 60 - (seconds ?? minutes * 60);
      return sizes.map((size, index) => {
        const value = (100 * Math.min(Math.max(done, 0), size)) / size;
        done -= size;
        return {
          value,
          weight: size,
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
      this.now.set(Date.now());
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
   * a finished one is left at once, and a running training is ended instead. */
  protected confirmLeaveGame(): void {
    if (this.game.finished()) {
      this.leaveGame();
      return;
    }
    if (this.endsTraining()) {
      this.confirmEndTraining();
      return;
    }
    this.confirm.ask(
      this.leaveLabel,
      $localize`:@@game.leaveText:Spiel auf diesem Gerät verlassen? Der bisherige Spielstand bleibt gespeichert.`,
      $localize`:@@game.leaveAction:Verlassen`,
      () => this.leaveGame(),
    );
  }

  private confirmEndTraining(): void {
    this.confirm.ask(
      this.endTrainingLabel,
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
