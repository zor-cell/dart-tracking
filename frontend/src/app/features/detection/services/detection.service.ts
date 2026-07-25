import { effect, inject, Injectable, signal } from '@angular/core';
import { SocketService } from '../../../core/socket/services/socket.service';
import { SettingsService } from '../../settings/services/settings.service';
import { DetectionFailureDto } from '../dto/detection-failure.dto';
import { DetectionResultDto } from '../dto/detection-result.dto';
import { GameStateDto } from '../../game/dto/game-state.dto';

/** How long a hit/failure line stays in the badge before it clears. */
const FEEDBACK_DURATION_MS = 2500;

// Fixed stroke colour per dart within a round — dart 1 / 2 / 3 each keep their
// own colour so all three throws stay readable side by side on the board. Chosen
// distinct from the board's yellow outline and from each other (cyan / pink /
// lime are still tellable apart for the common colour-vision deficiencies).
const DART_COLORS = [
  'rgba(56, 189, 248, 0.95)', // dart 1 — cyan
  'rgba(244, 114, 182, 0.95)', // dart 2 — pink
  'rgba(74, 222, 128, 0.95)', // dart 3 — lime
] as const;

const FAILURE_HINTS: Record<DetectionFailureDto, string> = {
  invalid_image: 'Bild nicht lesbar',
  not_calibrated: 'Erst kalibrieren',
  alignment_failed: 'Kamera hat sich bewegt',
  no_change: 'Kein Wurf erkannt',
};

/** One located dart to draw: its polylines plus the colour for its round index. */
export interface RoundDartOverlay {
  readonly polylines: number[][][];
  readonly color: string;
}

/**
 * The client half of dart detection: sends the triggered throw frame and tracks
 * the `detection_result` that comes back over the shared socket. Board detection
 * is server-side; this only forwards the frame and surfaces the outcome.
 *
 * The counterpart to `CalibrationService` — but the feedback lands in the
 * tracking badge rather than a toast, because detection runs continuously: a
 * toast on every false trigger would drown the screen. The score is never
 * touched here either; the server registers the hit and pushes an authoritative
 * `game_state` that `GameService` mirrors.
 */
@Injectable({ providedIn: 'root' })
export class DetectionService {
  private readonly socket = inject(SocketService);
  private readonly settings = inject(SettingsService);

  /**
   * The darts located in the current round, in throw order, each tagged with the
   * fixed colour for its index (dart 1 / 2 / 3). All darts of the round stay on
   * screen so the player sees the whole visit; the list is cleared when the round
   * turns over (see the `game_state` reconciliation below).
   *
   * Only *successful* detections are appended — a frame the server rejects
   * (`no_change`, an over-eager client trigger) must not leave a ghost outline
   * over a dart nobody landed.
   */
  readonly roundDarts = signal<readonly RoundDartOverlay[]>([]);

  /** Transient hit ("T20 · 60") or failure hint, shown briefly in the badge. */
  readonly feedbackLabel = signal<string | null>(null);

  private feedbackTimeoutId: ReturnType<typeof setTimeout> | null = null;
  // The turn count from the last game_state, to spot a round boundary.
  private lastTurnCount: number | null = null;
  // The server auto-advances the visit on its final dart, so the new turn is
  // already open by the time that dart's game_state arrives. Clearing then would
  // wipe the completed visit the instant it is done. Instead the boundary only
  // arms this flag; the darts stay on screen until the *next* visit's first dart
  // is located, and the append clears them.
  private visitEnded = false;

  constructor() {
    effect(() => {
      const message = this.socket.lastMessage();
      switch (message?.type) {
        case 'detection_result':
          this.handleDetectionResult(message);
          break;
        case 'game_state':
          this.reconcileRound(message.state.turns);
          break;
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
    // The first dart after a visit ended opens a fresh set, dropping the
    // previous visit's outlines that lingered so the player could read them.
    const startFresh = this.visitEnded;
    this.visitEnded = false;
    this.roundDarts.update((darts) => {
      const base = startFresh ? [] : darts;
      // Cap the colour lookup: an over-eager trigger can land more than three
      // detections in a visit, but there are only three dart colours.
      const color = DART_COLORS[Math.min(base.length, DART_COLORS.length - 1)];
      return [...base, { polylines, color }];
    });
  }

  /**
   * Keep the drawn darts in step with the authoritative turn history:
   * - a new turn (count up) means the visit auto-advanced on its final dart —
   *   arm the deferred clear but leave the finished visit on screen;
   * - a removed turn (count down) is an undo back into the previous visit —
   *   start clean, the reopened visit's darts were never tracked here;
   * - same turn, fewer darts is an in-visit undo — trim to the real count. Never
   *   grow here: appending is the detection result's job, which always arrives
   *   before its game_state (see core/socket.py).
   */
  private reconcileRound(turns: GameStateDto['turns']): void {
    const count = turns.length;
    if (this.lastTurnCount !== null) {
      if (count > this.lastTurnCount) {
        this.visitEnded = true;
      } else if (count < this.lastTurnCount) {
        this.roundDarts.set([]);
        this.visitEnded = false;
      } else {
        const dartCount = turns.at(-1)?.darts.length ?? 0;
        this.roundDarts.update((darts) =>
          darts.length > dartCount ? darts.slice(0, dartCount) : darts,
        );
      }
    }
    this.lastTurnCount = count;
  }

  /** Send a triggered throw frame; the result arrives asynchronously. */
  async submitFrame(frame: Blob): Promise<void> {
    this.clearFeedback();
    await this.socket.sendFrame('detection_frame', frame, this.settings.debugDetection());
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

function formatHit(segment: string | null, points: number | null): string {
  if (!segment) {
    return 'Treffer';
  }
  return points === null ? segment : `${segment} · ${points}`;
}

function hintFor(failure: DetectionFailureDto | null): string {
  return (failure && FAILURE_HINTS[failure]) ?? 'Kein Wurf erkannt';
}
