import { computed, inject, Injectable, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CalibrationFailureDto } from '../dto/calibration-failure.dto';
import { CalibrationState } from '../dto/calibration-state.dto';
import { captureFrameAsJpeg } from '../../camera/models/frame-capture';
import { SocketService } from '../../../core/socket/services/socket.service';

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

// What a device without a camera is told about the scoring camera's attempt;
// the advice above is addressed to whoever holds that camera.
const REMOTE_FAILURE_MESSAGE = 'Die Kamera konnte das Board nicht erkennen.';

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

  readonly status = signal<CalibrationStatus>('idle');

  /**
   * The detected board as polylines in normalized image coordinates, or null
   * whenever there is nothing freshly confirmed to draw. Cleared the moment an
   * attempt starts and left cleared if it fails: an outline that outlives the
   * measurement it came from is drawn over a board nobody just verified, so it
   * reads as a confirmation it no longer is.
   */
  readonly overlay = signal<number[][][] | null>(null);

  /** How far the game's calibration is, as the server reports it; null until it said. */
  readonly roomState = signal<CalibrationState | null>(null);

  /** Why this device's last calibration attempt failed; null once one succeeds. */
  readonly failureMessage = signal<string | null>(null);

  /** The failure a device without a camera shows. */
  readonly roomFailureMessage = computed(() =>
    this.roomState() === 'failed' ? REMOTE_FAILURE_MESSAGE : null,
  );

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
          this.failureMessage.set(null);
        } else {
          this.reportFailure(result.failure);
        }
      });

    this.socket
      .on('calibration_state')
      .pipe(takeUntilDestroyed())
      .subscribe(({ state }) => {
        this.roomState.set(state);
        if (state === 'calibrated') {
          this.failureMessage.set(null);
        }
      });
  }

  /** Ask the game's cameras to calibrate again; the outcome arrives as `calibration_state`. */
  requestCalibration(): void {
    this.socket.send({ type: 'request_calibration' });
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
    this.failureMessage.set(null);
  }

  private reportFailure(failure: CalibrationFailureDto | null): void {
    this.failureMessage.set((failure && FAILURE_MESSAGES[failure]) ?? UNKNOWN_FAILURE_MESSAGE);
  }
}
