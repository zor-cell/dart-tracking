import { computed, effect, inject, Injectable, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { SocketService } from '../../../core/socket/services/socket.service';
import { SettingsService } from '../../settings/services/settings.service';
import { GameService } from '../../game/services/game.service';
import { DetectionFailureDto } from '../dto/detection-failure.dto';
import { DetectionResultDto } from '../dto/detection-result.dto';
import { ThrowTriggerDto } from '../dto/throw-trigger.dto';
import { DartDto } from '../../game/dto/dart.dto';
import { GameStateDto } from '../../game/dto/game-state.dto';
import { dartColor } from '../../game/models/dart-colors';

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
 * A traceable step in the detect→send→answer cycle, for the client debug log.
 * `sent` is a frame leaving for the server (a client trigger fired); `hit` and
 * `rejected` are what came back. Made visible because the badge flashes past too
 * fast to tell *when* a frame actually went out and what the server made of it.
 */
export type DetectionEventKind = 'sent' | 'hit' | 'rejected';

export interface DetectionEvent {
  readonly seq: number; // running index, so a repeated label is still distinct
  readonly time: string; // wall-clock HH:MM:SS.d, tenth-second resolution
  readonly kind: DetectionEventKind;
  readonly label: string;
}

// How many recent events the debug log keeps. Enough to see a full visit's
// worth of triggers and answers without the list running off the screen.
const MAX_EVENTS = 12;

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
  private readonly game = inject(GameService);

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

  /** Whether a tracked throw could still be booked — the same rule the keypad
   * greys its keys out by. */
  readonly acceptsThrows = this.game.acceptsDarts;

  /**
   * Recent detect→send→answer events, newest first — the persistent trace behind
   * the fleeting badge, shown only in the client debug view.
   */
  readonly events = signal<readonly DetectionEvent[]>([]);
  private eventSeq = 0;

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
      const turns = this.game.state()?.turns;
      if (turns) {
        this.reconcileRound(turns);
      }
    });
  }

  private handleDetectionResult(message: DetectionResultDto): void {
    if (message.success) {
      if (message.overlay) {
        this.appendDart(message.overlay);
      }
      const label = formatHit(message.segment, message.points);
      this.showFeedback(label);
      this.logEvent('hit', label);
    } else {
      const label = hintFor(message.failure);
      this.showFeedback(label);
      this.logEvent('rejected', label);
    }
  }

  private appendDart(polylines: number[][][]): void {
    // A result for a visit that can take no more darts is a phantom trigger:
    // someone walking up to the board while the confirm tap is pending.
    if (!this.acceptsThrows()) {
      return;
    }
    const dartIndex = this.game.currentTurn()?.darts.length ?? 0;
    this.roundDarts.update((darts) => [
      ...darts,
      { polylines, dartIndex, color: dartColor(dartIndex), tip: null },
    ]);
  }

  /**
   * Keep the drawn darts in step with the authoritative turn history: a turn
   * boundary retires them all, within the turn each is placed again by its tip.
   * Never grows here — appending is the detection result's job.
   */
  private reconcileRound(turns: GameStateDto['turns']): void {
    const count = turns.length;
    const darts = turns.at(-1)?.darts ?? [];
    if (this.lastTurnCount !== null && count !== this.lastTurnCount) {
      this.roundDarts.set([]);
    } else {
      this.roundDarts.update((overlays) => overlays.flatMap((o) => place(o, darts)));
    }
    this.lastTurnCount = count;
  }

  /** Send a triggered throw frame; the result arrives asynchronously. */
  async submitFrame(frame: Blob, trigger: ThrowTriggerDto | null): Promise<void> {
    this.clearFeedback();
    // Log the send *before* awaiting: this is the exact moment a client trigger
    // turned into a frame leaving the device, which is what the log is meant to
    // pin down. The matching `hit`/`rejected` follows when the server answers.
    this.logEvent('sent', `${(frame.size / 1024).toFixed(0)} kB`);
    await this.socket.sendFrame(
      'detection_frame',
      frame,
      this.settings.debugDetection(),
      trigger ?? undefined,
    );
  }

  private logEvent(kind: DetectionEventKind, label: string): void {
    const event: DetectionEvent = { seq: this.eventSeq++, time: nowStamp(), kind, label };
    this.events.update((events) => [event, ...events].slice(0, MAX_EVENTS));
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
function nowStamp(): string {
  const now = new Date();
  const pad = (value: number) => value.toString().padStart(2, '0');
  const tenth = Math.floor(now.getMilliseconds() / 100);
  return `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}.${tenth}`;
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

/** Where an outline belongs in the visit as it now stands, or nothing when the
 * dart it marked is gone. A fresh outline takes its tip from the dart booked at
 * its place, and is looked up by that point from then on. */
function place(overlay: RoundDartOverlay, darts: readonly DartDto[]): RoundDartOverlay[] {
  const tip = overlay.tip ?? darts[overlay.dartIndex]?.position ?? null;
  const dartIndex = tip === null ? overlay.dartIndex : darts.findIndex((d) => sameTip(d.position, tip));
  if (dartIndex < 0 || dartIndex >= darts.length) {
    return [];
  }
  return [{ ...overlay, tip, dartIndex, color: dartColor(dartIndex) }];
}

function sameTip(
  a: readonly [number, number] | null,
  b: readonly [number, number],
): boolean {
  return a !== null && a[0] === b[0] && a[1] === b[1];
}
