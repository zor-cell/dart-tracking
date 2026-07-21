import { computed, effect, inject, Injectable, signal, untracked } from '@angular/core';
import { NotificationService } from '../../../core/services/notification.service';
import { CalibrationFailure } from '../dto/calibration-failure';
import { captureFrameAsJpeg } from '../models/frame-capture';
import { SocketService } from './socket.service';

export type CalibrationStatus = 'idle' | 'pending' | 'success' | 'error';

/**
 * What the user should change, per failing stage. Phrased as an instruction
 * rather than a diagnosis — the cause only matters here insofar as it implies
 * a different fix.
 */
const FAILURE_MESSAGES: Record<CalibrationFailure, string> = {
  invalid_image: 'Das Kamerabild konnte nicht gelesen werden. Bitte erneut versuchen.',
  no_coloured_region: 'Kein Board erkannt. Näher an das Board gehen und für bessere Beleuchtung sorgen.',
  ellipse_fit_failed: 'Board-Umriss nicht erkennbar. Das gesamte Board ins Bild nehmen.',
  sector_wires_unclear:
    'Board nur teilweise erkannt. Verdeckungen und starke Schatten auf dem Board vermeiden.',
  homography_failed:
    'Board-Position konnte nicht berechnet werden. Kamera ruhig halten und erneut versuchen.',
};

const UNKNOWN_FAILURE_MESSAGE = 'Bitte erneut versuchen.';

const FAILURE_TITLE = 'Kalibrierung fehlgeschlagen';

/** Long enough to read an instruction and act on it, short enough to go away. */
const FAILURE_TOAST_LIFE = 8000;

/**
 * Board calibration: capture the current video frame, send it as a
 * `calibration_frame` and track the `calibration_result` that comes back over
 * the shared socket. Board detection itself is server-side (see
 * backend/.../features/tracking/services/board_detector.py).
 *
 * Can be run again at any time — the server replaces the stored calibration —
 * which is how the user recovers after the board or camera is knocked out of
 * place.
 */
@Injectable({ providedIn: 'root' })
export class CalibrationService {
  private readonly socket = inject(SocketService);
  private readonly notifications = inject(NotificationService);

  readonly status = signal<CalibrationStatus>('idle');

  private readonly lastOverlay = signal<number[][][] | null>(null);

  /**
   * The detected board as polylines in normalized image coordinates — but null
   * while an attempt is running: the drawing describes a board position that is
   * in the middle of being re-measured, and leaving it up would make a stale
   * outline read as a fresh confirmation. A failed attempt brings it back,
   * since the calibration it came from is still the one in effect.
   */
  readonly overlay = computed(() => (this.status() === 'pending' ? null : this.lastOverlay()));

  constructor() {
    effect(() => {
      const message = this.socket.lastMessage();
      // `status` is read untracked on purpose: this must run when a reply
      // arrives, never merely because the status changed. Tracking it would
      // make entering 'pending' re-trigger the effect while the *previous*
      // reply is still the last message, resolving the new request from the
      // old result — which is what happens for real, since detection takes
      // long enough that the effect runs well before the answer arrives.
      if (message?.type !== 'calibration_result' || untracked(this.status) !== 'pending') {
        return;
      }
      this.status.set(message.success ? 'success' : 'error');
      if (message.success) {
        this.lastOverlay.set(message.overlay);
      } else {
        this.reportFailure(message.failure);
      }
    });
  }

  async calibrate(video: HTMLVideoElement, canvas: HTMLCanvasElement): Promise<void> {
    this.status.set('pending');
    const frame = await captureFrameAsJpeg(video, canvas);
    await this.socket.sendFrame('calibration_frame', frame);
  }

  reset(): void {
    this.status.set('idle');
    this.lastOverlay.set(null);
  }

  /**
   * Failures are transient toasts rather than something pinned to the preview:
   * the whole point of this screen is seeing the camera, so an advice text that
   * never leaves ends up hiding the very thing it asks the user to fix.
   */
  private reportFailure(failure: CalibrationFailure | null): void {
    // A value the server added but this build does not know yet still has to
    // say something useful.
    const message = (failure && FAILURE_MESSAGES[failure]) ?? UNKNOWN_FAILURE_MESSAGE;
    this.notifications.showErrorMessage(message, FAILURE_TITLE, FAILURE_TOAST_LIFE);
  }
}
