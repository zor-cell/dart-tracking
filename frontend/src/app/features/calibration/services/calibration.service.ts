import { effect, inject, Injectable, signal, untracked } from '@angular/core';
import { NotificationService } from '../../../core/notification/services/notification.service';
import { CalibrationFailureDto } from '../dto/calibration-failure.dto';
import { CalibrationStatusDto } from '../dto/calibration-status.dto';
import { captureFrameAsJpeg } from '../../camera/models/frame-capture';
import { SocketService } from '../../../core/socket/services/socket.service';
import { SettingsService } from '../../settings/services/settings.service';

export type CalibrationStatus = 'idle' | 'pending' | 'success' | 'error';

const FAILURE_MESSAGES: Record<CalibrationFailureDto, string> = {
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

// What a device without a camera is told about another device's attempt: it
// cannot see the board, so the advice above ("get closer", "avoid shadows") is
// addressed to someone else and only the fact belongs here.
const REMOTE_FAILURE_MESSAGE = 'Die Kamera konnte das Board nicht erkennen.';
const REMOTE_SUCCESS_MESSAGE = 'Board neu kalibriert.';

/**
 * Board calibration: capture the current video frame, send it as a
 * `calibration_frame` and track the `calibration_result` that comes back over
 * the shared socket. Board detection itself is server-side (see
 * backend/src/app/api/features/tracking/services/board_detector.py).
 *
 * Can be run again at any time — the server replaces the stored calibration —
 * which is how the user recovers after the board or camera is knocked out of
 * place. It need not be this device that decides so: `requestCalibration` asks
 * the game's cameras, and the end of a visit does the same server-side.
 */
@Injectable({ providedIn: 'root' })
export class CalibrationService {
  private readonly socket = inject(SocketService);
  private readonly notifications = inject(NotificationService);
  private readonly settings = inject(SettingsService);

  readonly status = signal<CalibrationStatus>('idle');

  /**
   * The detected board as polylines in normalized image coordinates, or null
   * whenever there is nothing freshly confirmed to draw. Cleared the moment an
   * attempt starts and left cleared if it fails: an outline that outlives the
   * measurement it came from is drawn over a board nobody just verified, so it
   * reads as a confirmation it no longer is.
   */
  readonly overlay = signal<number[][][] | null>(null);

  // Whether this device asked for the recalibration that is currently out.
  // Only then is a *successful* one worth a toast: it is the answer to a tap
  // that otherwise looks like it did nothing. The ones the round change fires
  // would be a toast per visit.
  private awaitingRequest = false;

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

    // How a device learns about a calibration that was not its own — the only
    // route for one without a camera, since `calibration_result` goes to the
    // camera that produced it alone (docs/feature/multi-device.md §3). Reaches
    // the device that asked for the recalibration and no other, so no attempt
    // is ever reported twice here.
    effect(() => {
      const message = this.socket.lastMessage();
      if (message?.type !== 'calibration_status') {
        return;
      }
      untracked(() => this.reportRemoteStatus(message));
    });
  }

  /**
   * Ask the game's cameras to calibrate again. What a device without a picture
   * of its own has instead of the calibrate button; each camera answers from
   * its own frame, and what comes back here is `calibration_status`.
   */
  requestCalibration(): void {
    this.awaitingRequest = true;
    this.socket.send({ type: 'request_calibration' });
  }

  async calibrate(video: HTMLVideoElement, canvas: HTMLCanvasElement): Promise<void> {
    this.status.set('pending');
    this.overlay.set(null);
    const frame = await captureFrameAsJpeg(video, canvas);
    await this.socket.sendFrame('calibration_frame', frame, this.settings.debugCalibration());
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
  private reportFailure(failure: CalibrationFailureDto | null): void {
    const message = (failure && FAILURE_MESSAGES[failure]) ?? UNKNOWN_FAILURE_MESSAGE;
    this.notifications.showErrorMessage(message, FAILURE_TITLE, FAILURE_TOAST_LIFE);
  }

  /**
   * Report a camera's attempt to the device that asked for it. Failures always:
   * from here on nothing is scored on that camera. Success only in answer to a
   * tap of our own — the ones a round change fires would be a toast per visit.
   */
  private reportRemoteStatus(status: CalibrationStatusDto): void {
    const requested = this.awaitingRequest;
    this.awaitingRequest = false;

    if (!status.success) {
      this.notifications.showErrorMessage(
        REMOTE_FAILURE_MESSAGE,
        FAILURE_TITLE,
        FAILURE_TOAST_LIFE,
      );
    } else if (requested) {
      this.notifications.showSuccess(REMOTE_SUCCESS_MESSAGE);
    }
  }
}
