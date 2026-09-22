import { inject, Injectable, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NotificationService } from '../../../core/notification/services/notification.service';
import { CalibrationFailureDto } from '../dto/calibration-failure.dto';
import { CalibrationStatusDto } from '../dto/calibration-status.dto';
import { captureFrameAsJpeg } from '../../camera/models/frame-capture';
import { SocketService } from '../../../core/socket/services/socket.service';
import { SettingsService } from '../../settings/services/settings.service';

export type CalibrationStatus = 'idle' | 'pending' | 'success' | 'error';

const FAILURE_MESSAGES: Record<CalibrationFailureDto, string> = {
  invalid_image: 'Das Kamerabild konnte nicht gelesen werden. Bitte erneut versuchen.',
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
const REMOTE_TIMEOUT_MESSAGE = 'Keine Kamera hat geantwortet.';
// How long a requested recalibration may stay unanswered, in ms.
const REMOTE_TIMEOUT = 8000;

/**
 * Board calibration: capture the current video frame, send it as a
 * `calibration_frame` and track the `calibration_result` that comes back over
 * the shared socket. Board detection itself is server-side (see
 * backend/src/app/api/features/calibration/services/board_detector.py).
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

  /** Whether the game has a calibrated scoring camera; null until the server said. */
  readonly boardCalibrated = signal<boolean | null>(null);

  /** Whether this device asked for a recalibration that no camera has answered yet. */
  readonly requestPending = signal(false);

  private requestTimeout: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    this.socket
      .on('calibration_result')
      .pipe(takeUntilDestroyed())
      .subscribe((result) => {
        if (this.status() !== 'pending') {
          return;
        }
        this.status.set(result.success ? 'success' : 'error');
        if (result.success) {
          this.overlay.set(result.overlay);
        } else {
          this.reportFailure(result.failure);
        }
      });

    this.socket
      .on('calibration_state')
      .pipe(takeUntilDestroyed())
      .subscribe((state) => this.boardCalibrated.set(state.calibrated));

    // How a device learns about a calibration that was not its own — the only
    // route for one without a camera, since `calibration_result` goes to the
    // camera that produced it alone (docs/feature/done/multi-device.md §3). Reaches
    // the device that asked for the recalibration and no other, so no attempt
    // is ever reported twice here.
    this.socket
      .on('calibration_status')
      .pipe(takeUntilDestroyed())
      .subscribe((status) => this.reportRemoteStatus(status));
  }

  /**
   * Ask the game's cameras to calibrate again. What a device without a picture
   * of its own has instead of the calibrate button; each camera answers from
   * its own frame, and what comes back here is `calibration_status`.
   */
  requestCalibration(): void {
    this.clearRequest();
    this.requestPending.set(true);
    this.requestTimeout = setTimeout(() => {
      this.clearRequest();
      this.notifications.showErrorMessage(REMOTE_TIMEOUT_MESSAGE, FAILURE_TITLE, FAILURE_TOAST_LIFE);
    }, REMOTE_TIMEOUT);
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
   * Report a camera's attempt to the device that asked for it: stop the pending
   * indicator, and toast failures only — success is the indicator stopping.
   */
  private reportRemoteStatus(status: CalibrationStatusDto): void {
    this.clearRequest();
    if (!status.success) {
      this.notifications.showErrorMessage(
        REMOTE_FAILURE_MESSAGE,
        FAILURE_TITLE,
        FAILURE_TOAST_LIFE,
      );
    }
  }

  private clearRequest(): void {
    if (this.requestTimeout !== null) {
      clearTimeout(this.requestTimeout);
      this.requestTimeout = null;
    }
    this.requestPending.set(false);
  }
}
