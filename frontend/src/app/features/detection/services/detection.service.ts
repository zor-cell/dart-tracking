import { effect, inject, Injectable, signal } from '@angular/core';
import { SocketService } from '../../../core/socket/services/socket.service';
import { SettingsService } from '../../settings/services/settings.service';
import { DetectionFailureDto } from '../dto/detection-failure.dto';

/** How long a hit/failure line stays in the badge before it clears. */
const FEEDBACK_DURATION_MS = 2500;

const FAILURE_HINTS: Record<DetectionFailureDto, string> = {
  invalid_image: 'Bild nicht lesbar',
  not_calibrated: 'Erst kalibrieren',
  alignment_failed: 'Kamera hat sich bewegt',
  no_change: 'Kein Wurf erkannt',
};

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
   * The detected dart as polylines in normalized image coordinates, or null when
   * there is nothing freshly located to draw. Cleared the moment a new throw is
   * sent — an outline that outlives the throw it came from is drawn over a dart
   * nobody just measured — and left cleared on a failure.
   */
  readonly overlay = signal<number[][][] | null>(null);

  /** Transient hit ("T20 · 60") or failure hint, shown briefly in the badge. */
  readonly feedbackLabel = signal<string | null>(null);

  private feedbackTimeoutId: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    effect(() => {
      const message = this.socket.lastMessage();
      if (message?.type !== 'detection_result') {
        return;
      }
      if (message.success) {
        this.overlay.set(message.overlay);
        this.showFeedback(formatHit(message.segment, message.points));
      } else {
        this.overlay.set(null);
        this.showFeedback(hintFor(message.failure));
      }
    });
  }

  /** Send a triggered throw frame; the result arrives asynchronously. */
  async submitFrame(frame: Blob): Promise<void> {
    this.overlay.set(null);
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
