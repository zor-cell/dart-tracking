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
import { dartColor, SHADOW_DART_COLOR } from '../../game/models/dart-colors';

/** How long a hit/failure line stays in the badge before it clears. */
const FEEDBACK_DURATION_MS = 2500;

const FAILURE_HINTS: Record<DetectionFailureDto, string> = {
  invalid_image: 'Bild nicht lesbar',
  not_calibrated: 'Erst kalibrieren',
  alignment_failed: 'Kamera hat sich bewegt',
  no_change: 'Kein Wurf erkannt',
  implausible_shape: 'Board verdeckt',
  darts_removed: 'Pfeile entfernt',
};

/** One located dart to draw: its polylines, its place in the visit, and the
 * colour for that place. */
export interface RoundDartOverlay {
  readonly polylines: number[][][];
  readonly dartIndex: number;
  readonly color: string;
  /** The tip this outline was drawn at, in board millimetres — what it is
   * matched back to the visit by. Null until the state holding it has arrived. */
  readonly tip: readonly [number, number] | null;
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
  private readonly game = inject(GameService);
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

  /** Whether a tracked throw is still taken, as a booked or as a shadow dart. */
  readonly acceptsThrows = this.game.tracksThrows;

  /** Whether a captured frame goes to the server: a throw, or the darts being pulled. */
  readonly sendsFrames = computed(() => this.acceptsThrows() || this.game.watchesPull());

  private feedbackTimeoutId: ReturnType<typeof setTimeout> | null = null;
  // The turn count from the last reconciled state.
  private lastTurnCount: number | null = null;

  constructor() {
    // Located darts arrive over the socket, one `detection_result` per throw.
    this.socket
      .on('detection_result')
      .pipe(takeUntilDestroyed())
      .subscribe((result) => this.handleDetectionResult(result));

    // Round boundaries are reconciled off the game state itself, not the socket:
    // confirming a visit (the camera-mode "next player" tap) is an HTTP call that
    // updates the state without a socket push, so watching the socket alone would
    // miss it and leave the finished visit's outlines on the board. GameService
    // mirrors both the socket pushes and the HTTP responses, so this catches every
    // boundary.
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
    this.roundDarts.update((darts) => [
      ...darts,
      { polylines, dartIndex, color: colorFor(dartIndex, booked), tip: null },
    ]);
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
        overlays.flatMap((o) => place(o, darts, booked.length)),
      );
    }
    this.lastTurnCount = count;
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
  return points === null ? segment : `${segment} · ${points}`;
}

function hintFor(failure: DetectionFailureDto | null): string {
  return (failure && FAILURE_HINTS[failure]) ?? 'Kein Wurf erkannt';
}

/** Where an outline belongs in the visit as it now stands — booked darts, then
 * shadow darts — or nothing when the dart it marked is gone. Looked up by its tip. */
function place(
  overlay: RoundDartOverlay,
  darts: readonly DartDto[],
  booked: number,
): RoundDartOverlay[] {
  const tip = overlay.tip ?? darts[overlay.dartIndex]?.position ?? null;
  const dartIndex = tip === null ? overlay.dartIndex : darts.findIndex((d) => sameTip(d.position, tip));
  if (dartIndex < 0 || dartIndex >= darts.length) {
    return [];
  }
  return [{ ...overlay, tip, dartIndex, color: colorFor(dartIndex, booked) }];
}

function colorFor(dartIndex: number, booked: number): string {
  return dartIndex < booked ? dartColor(dartIndex) : SHADOW_DART_COLOR;
}

function sameTip(
  a: readonly [number, number] | null,
  b: readonly [number, number],
): boolean {
  return a !== null && a[0] === b[0] && a[1] === b[1];
}
