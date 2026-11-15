import { computed, effect, inject, Injectable, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { SocketService } from '../../../core/socket/services/socket.service';
import { GameService } from '../../game/services/game.service';
import { SettingsService } from '../../settings/services/settings.service';
import { DetectionFailureDto } from '../dto/detection-failure.dto';
import { DetectionResultDto } from '../dto/detection-result.dto';
import { ThrowTriggerDto } from '../dto/throw-trigger.dto';
import { DartDto } from '../../game/dto/dart.dto';
import { GameStateDto } from '../../game/dto/game-state.dto';
import { locatedDart, placeOverlay, RoundDartOverlay } from '../models/round-dart-overlay';

/** How long a hit/failure line stays in the badge before it clears. */
const FEEDBACK_DURATION_MS = 2500;

const FAILURE_HINTS: Record<DetectionFailureDto, string> = {
  invalid_image: $localize`:@@detection.invalidImage:Bild nicht lesbar`,
  not_calibrated: $localize`:@@detection.notCalibrated:Erst kalibrieren`,
  alignment_failed: $localize`:@@detection.moved:Kamera hat sich bewegt`,
  no_change: $localize`:@@detection.noThrow:Kein Wurf erkannt`,
  implausible_shape: $localize`:@@detection.covered:Board verdeckt`,
  darts_removed: $localize`:@@detection.removed:Darts entfernt`,
};

/**
 * The client half of dart detection: sends the triggered throw frame and tracks
 * the `detection_result`, shown in the tracking badge.
 */
@Injectable({ providedIn: 'root' })
export class DetectionService {
  private readonly socket = inject(SocketService);
  private readonly game = inject(GameService);
  private readonly settings = inject(SettingsService);

  /**
   * The darts located in the current round in throw order, each with the colour of
   * its index; only successful detections, cleared when the round turns over.
   */
  readonly roundDarts = signal<readonly RoundDartOverlay[]>([]);

  /** Transient hit ("T20 (60)") or failure hint, shown briefly in the badge. */
  readonly feedbackLabel = signal<string | null>(null);

  /** Whether a tracked throw is still taken, as a booked or as a shadow dart. */
  readonly acceptsThrows = this.game.tracksThrows;

  /** Whether a captured frame goes to the server: a throw, or the darts being pulled. */
  readonly sendsFrames = computed(() => this.acceptsThrows() || this.game.watchesPull());

  private feedbackTimeoutId: ReturnType<typeof setTimeout> | null = null;
  // The turn count and the open visit's dart count from the last reconciled state.
  private lastTurnCount: number | null = null;
  private lastDartCount = 0;

  constructor() {
    // Located darts arrive over the socket, one `detection_result` per throw.
    this.socket
      .on('detection_result')
      .pipe(takeUntilDestroyed())
      .subscribe((result) => this.handleDetectionResult(result));

    // Reconcile the round's darts with every game state.
    effect(() => {
      const state = this.game.state();
      if (state) {
        this.reconcileRound(state.turns, state.shadowDarts);
      }
    });
  }

  private handleDetectionResult(message: DetectionResultDto): void {
    if (message.success) {
      if (message.overlay) {
        this.appendDart(message.overlay);
      }
      this.showFeedback(formatHit(message.segment, message.points));
    } else {
      this.showFeedback(hintFor(message.failure));
    }
  }

  private appendDart(polylines: number[][][]): void {
    // A result for a visit that can take no more darts is a phantom trigger:
    // someone walking up to the board while the confirm tap is pending.
    if (!this.acceptsThrows()) {
      return;
    }
    const booked = this.game.currentTurn()?.darts.length ?? 0;
    const dartIndex = booked + this.game.shadowDarts().length;
    this.roundDarts.update((darts) => [...darts, locatedDart(polylines, dartIndex, booked)]);
  }

  /**
   * Keep the drawn darts in step with the authoritative turn history: a turn
   * boundary retires them all, within the turn each is placed again by its tip.
   * Never grows here — appending is the detection result's job.
   */
  private reconcileRound(turns: GameStateDto['turns'], shadows: readonly DartDto[]): void {
    const count = turns.length;
    const booked = turns.at(-1)?.darts ?? [];
    const darts = [...booked, ...shadows];
    if (this.lastTurnCount !== null && count !== this.lastTurnCount) {
      this.roundDarts.set([]);
    } else {
      this.roundDarts.update((overlays) =>
        overlays.flatMap((o) => placeOverlay(o, darts, booked.length, this.lastDartCount)),
      );
    }
    this.lastTurnCount = count;
    this.lastDartCount = darts.length;
  }

  /** Send a triggered throw frame; the result arrives asynchronously. */
  async submitFrame(frame: Blob, trigger: ThrowTriggerDto | null): Promise<void> {
    this.clearFeedback();
    const testRun = this.game.state()?.evaluationEnabled ?? false;
    await this.socket.sendFrame('detection_frame', frame, {
      trigger: trigger && !testRun ? { ...trigger, snapshots: [] } : (trigger ?? undefined),
      advanceOnPull: this.settings.advanceOnPull(),
    });
  }

  private showFeedback(label: string): void {
    this.clearFeedback();
    this.feedbackLabel.set(label);
    this.feedbackTimeoutId = setTimeout(() => this.feedbackLabel.set(null), FEEDBACK_DURATION_MS);
  }

  private clearFeedback(): void {
    if (this.feedbackTimeoutId !== null) {
      clearTimeout(this.feedbackTimeoutId);
      this.feedbackTimeoutId = null;
    }
    this.feedbackLabel.set(null);
  }
}

/** Wall-clock stamp at tenth-second resolution, e.g. "14:03:21.7". */
function formatHit(segment: string | null, points: number | null): string {
  if (!segment) {
    return 'Treffer';
  }
  return points === null ? segment : `${segment} (${points})`;
}

function hintFor(failure: DetectionFailureDto | null): string {
  return (failure && FAILURE_HINTS[failure]) ?? FAILURE_HINTS.no_change;
}
