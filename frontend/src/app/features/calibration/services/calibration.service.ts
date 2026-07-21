import { effect, inject, Injectable, signal, untracked } from '@angular/core';
import { NotificationService } from '../../../core/notification/services/notification.service';
import { CalibrationFailure } from '../dto/calibration-failure';
import { captureFrameAsJpeg } from '../../camera/models/frame-capture';
import { SocketService } from '../../../core/socket/services/socket.service';

export type CalibrationStatus = 'idle' | 'pending' | 'success' | 'error';

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
const FAILURE_TOAST_LIFE = 8000;

/**
 * Board calibration: capture the current video frame, send it as a
 * `calibration_frame` and track the `calibration_result` that comes back over
 * the shared socket. Board detection itself is server-side (see
 * backend/src/app/api/features/tracking/services/board_detector.py).
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

  /**
   * The detected board as polylines in normalized image coordinates, or null
   * whenever there is nothing freshly confirmed to draw. Cleared the moment an
   * attempt starts and left cleared if it fails: an outline that outlives the
   * measurement it came from is drawn over a board nobody just verified, so it
   * reads as a confirmation it no longer is.
   */
  readonly overlay = signal<number[][][] | null>(null);

  constructor() {
    effect(() => {
      const message = this.socket.lastMessage();
      if (message?.type !== 'calibration_result' || untracked(this.status) !== 'pending') {
        return;
      }
      this.status.set(message.success ? 'success' : 'error');
      if (message.success) {
        this.overlay.set(message.overlay);
      } else {
        this.reportFailure(message.failure);
      }
    });
  }

  async calibrate(video: HTMLVideoElement, canvas: HTMLCanvasElement): Promise<void> {
    this.status.set('pending');
    this.overlay.set(null);
    const frame = await captureFrameAsJpeg(video, canvas);
    await this.socket.sendFrame('calibration_frame', frame);
  }

  reset(): void {
    this.status.set('idle');
    this.overlay.set(null);
  }

  /**
   * Failures are transient toasts rather than something pinned to the preview:
   * the whole point of this screen is seeing the camera, so an advice text that
   * never leaves ends up hiding the very thing it asks the user to fix.
   */
  private reportFailure(failure: CalibrationFailure | null): void {
    const message = (failure && FAILURE_MESSAGES[failure]) ?? UNKNOWN_FAILURE_MESSAGE;
    this.notifications.showErrorMessage(message, FAILURE_TITLE, FAILURE_TOAST_LIFE);
  }
}
