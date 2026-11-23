import { Injectable, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CalibrationService } from '../../calibration/services/calibration.service';
import { captureFrameAsJpeg } from '../../camera/models/frame-capture';
import { CameraService } from '../../camera/services/camera.service';
import { FrameDiffService } from '../../detection/services/frame-diff.service';
import { DeviceRole } from '../../../core/socket/models/device-role';
import { SocketService } from '../../../core/socket/services/socket.service';
import { NotificationService } from '../../../core/notification/services/notification.service';
import { CameraPhase } from '../models/camera-phase';
import { GameService } from './game.service';
import { readStored, writeStored } from '../../../core/storage/models/browser-storage';

// Session storage key of the camera phase, so a refresh can resume it.
const PHASE_KEY = 'dart-tracking.cameraPhase';

// Whether this device filmed its last game, so the next one starts the camera itself.
const CAMERA_USED_KEY = 'dart-tracking.cameraUsed';

// Time a restarted camera gets to settle its auto exposure before a frame is used, in ms.
const CAMERA_SETTLE_MS = 1500;

// Set once this device was told that games keep their camera frames.
const FRAMES_NOTICE_KEY = 'dart-tracking.framesNotice';

// How long the frames notice stays up, in ms.
const FRAMES_NOTICE_LIFE_MS = 12000;

/**
 * Owns this device's camera session: its phase and the detection loop. Survives
 * route changes (`attachView`, `detachView`), ends on `endSession`, and resumes
 * after a refresh.
 */
@Injectable({ providedIn: 'root' })
export class GameSessionService {
  private readonly camera = inject(CameraService);
  private readonly calibration = inject(CalibrationService);
  private readonly throwCapture = inject(FrameDiffService);
  private readonly game = inject(GameService);
  private readonly socket = inject(SocketService);
  private readonly notifications = inject(NotificationService);

  readonly phase = signal<CameraPhase>('idle');
  readonly cameraError = this.camera.error;

  /** What this device does in the game — the server's answer, read here to pick
   * the view. `null` until the handshake has answered. */
  readonly role = this.socket.role.asReadonly();

  // The current view's elements, set by the mounted game component. Undefined
  // while no game view is on screen.
  private video?: HTMLVideoElement;
  private diffCanvas?: HTMLCanvasElement;
  private captureCanvas?: HTMLCanvasElement;

  // The phase from before a refresh, captured once at construction. Consumed by
  // restore() to seed pendingResumePhase.
  private persistedPhase = readStored(PHASE_KEY, 'session') as CameraPhase | null;

  // Phase to resume the camera into on the next view attach, set by restore()
  // after a reload once the game is confirmed. Consumed once the elements exist.
  private pendingResumePhase: CameraPhase | null = null;

  // A calibration asked for while no camera view was mounted, run on the next
  // attach.
  private pendingCalibration = false;

  constructor() {
    effect(() => {
      if (this.calibration.status() === 'success' && this.phase() === 'calibrating') {
        this.startTracking();
      }
    });

    // Lock the picture as the board was calibrated in; the reference frame is this one.
    effect(() => {
      if (this.calibration.status() === 'success') {
        void this.camera.lockExposure();
      }
    });

    // A recalibration asked for elsewhere, answered if this device's camera runs.
    this.socket
      .on('calibration_requested')
      .pipe(takeUntilDestroyed())
      .subscribe(() => {
        if (this.phase() !== 'idle') {
          void this.calibrate();
        }
      });

    // A handover's check that the calibration still fits, answered while tracking.
    this.socket
      .on('board_check_requested')
      .pipe(takeUntilDestroyed())
      .subscribe(() => {
        if (this.phase() === 'tracking') {
          void this.sendBoardCheck();
        }
      });

    // Mirror the live phase into storage so a refresh can resume from it.
    effect(() => {
      const phase = this.phase();
      writeStored(PHASE_KEY, phase === 'idle' ? null : phase, 'session');
    });
  }

  /** Wire the mounted game view's elements into the session. */
  attachView(
    video: HTMLVideoElement,
    diffCanvas: HTMLCanvasElement,
    captureCanvas: HTMLCanvasElement,
  ): void {
    this.video = video;
    this.diffCanvas = diffCanvas;
    this.captureCanvas = captureCanvas;

    if (this.phase() !== 'idle') {
      this.camera.attachTo(video);
      const playing = video.play().catch(() => {});

      if (this.phase() === 'tracking') {
        this.runDetectionLoop();
      }
      // Awaited: before playback starts the element has no frame to capture.
      if (this.pendingCalibration) {
        void playing.then(() => this.calibrate());
      }
      return;
    }

    // First attach after a full reload: the elements now exist, so resume the
    // camera into the phase restore() captured (if the session had one running).
    const target = this.pendingResumePhase;
    this.pendingResumePhase = null;
    if (target === 'tracking' || target === 'calibrating') {
      void this.resume(target);
    } else if (this.startsCamera()) {
      void this.startCamera();
    }
  }

  /** Whether an open game on a camera device that filmed the last one films again unasked. */
  private startsCamera(): boolean {
    return (
      this.role() === 'camera' &&
      this.game.winner() === null &&
      !this.game.ended() &&
      readStored(CAMERA_USED_KEY) === 'true'
    );
  }

  /** Detach the game view on unmount: pause the loop only; keep camera + socket. */
  detachView(): void {
    this.throwCapture.stopDetectionLoop();
    this.video = undefined;
    this.diffCanvas = undefined;
    this.captureCanvas = undefined;
  }

  /** Start the camera for a fresh session (the "Kamera starten" tap). */
  async startCamera(): Promise<void> {
    if (!this.game.peekGameId() || !(await this.acquireCamera())) {
      return;
    }
    this.calibration.reset();
    this.phase.set('calibrating');
    this.noticeFramesKept();
  }

  /** Say once per device that this game keeps its camera frames, and where to stop it. */
  private noticeFramesKept(): void {
    if (!this.game.state()?.evaluationEnabled || readStored(FRAMES_NOTICE_KEY) === 'true') {
      return;
    }
    writeStored(FRAMES_NOTICE_KEY, 'true');
    this.notifications.showInfo(
      $localize`:@@game.framesNotice:Von diesem Spiel werden die Kamerabilder gespeichert, damit die Erkennung besser wird. Wer das Spiel angelegt hat, kann das in den Einstellungen abschalten.`,
      undefined,
      FRAMES_NOTICE_LIFE_MS,
    );
  }

  /**
   * Set what this device does: on the way into a game, or from the switch in the
   * game view. A no-op when it already holds; dropping the camera role ends a live session.
   */
  setRole(role: DeviceRole): void {
    if (role === this.role()) {
      return;
    }
    this.socket.setRole(role);
    if (role === 'scoreboard') {
      writeStored(CAMERA_USED_KEY, null);
      this.endSession();
    }
  }

  /** Capture the current frame for board calibration. With no view mounted there
   * is no frame to send: the attempt is held over to the next attach, and the
   * outline of the last one drops with it. */
  async calibrate(): Promise<void> {
    if (!this.video || !this.captureCanvas) {
      this.pendingCalibration = true;
      this.calibration.reset();
      return;
    }
    this.pendingCalibration = false;
    await this.calibration.calibrate(this.video, this.captureCanvas);
  }

  /** End the game: full teardown of the live session. The socket goes down with
   * the game itself (`GameService.reset`), not here. */
  endSession(): void {
    this.throwCapture.stopDetectionLoop();
    this.camera.stop();
    this.calibration.reset();
    this.pendingCalibration = false;
    this.phase.set('idle');
  }

  /**
   * Refetch the game when the game view initialises and stash the camera phase
   * to resume on the next view attach; cleared if there is no game.
   */
  async restore(): Promise<boolean> {
    // Only a filming device stores a phase, so no role check.
    this.pendingResumePhase = this.persistedPhase;
    this.persistedPhase = null;

    const restored = await this.game.ensureRestored();
    if (!restored) {
      this.pendingResumePhase = null; // no game, or the server forgot it → stay idle
    }
    return restored;
  }

  /** Leave the game on this device: the live session and the cached game go. */
  leave(): void {
    if (this.phase() === 'idle') {
      writeStored(CAMERA_USED_KEY, null);
    }
    this.endSession();
    this.game.reset();
  }

  /** Restart the camera after a refresh, landing in the phase the session was
   * in. Tracking recalibrates on the new stream while the board is empty, and
   * keeps the server-side calibration while darts are in it. */
  private async resume(target: CameraPhase): Promise<void> {
    if (!this.game.peekGameId() || !(await this.acquireCamera())) {
      return;
    }
    if (target !== 'tracking') {
      this.phase.set(target);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, CAMERA_SETTLE_MS));
    if (!this.game.peekGameId()) {
      return;
    }
    if (this.boardEmpty()) {
      this.phase.set('calibrating');
      await this.calibrate();
      return;
    }
    this.phase.set('tracking');
    this.runDetectionLoop();
    await this.camera.lockExposure();
  }

  private boardEmpty(): boolean {
    return !this.game.currentTurn()?.darts.length && this.game.shadowDarts().length === 0;
  }

  private startTracking(): void {
    this.runDetectionLoop();
    this.phase.set('tracking');
  }

  private runDetectionLoop(): void {
    if (this.video && this.diffCanvas && this.captureCanvas) {
      this.throwCapture.stopDetectionLoop();
      this.throwCapture.startDetectionLoop(this.video, this.diffCanvas, this.captureCanvas);
    }
  }

  private async sendBoardCheck(): Promise<void> {
    if (this.video && this.captureCanvas) {
      const frame = await captureFrameAsJpeg(this.video, this.captureCanvas);
      await this.socket.sendFrame('board_check_frame', frame);
    }
  }

  /** Point the current video element at a freshly started stream; on denial the
   * session falls back to idle. Returns whether the camera came up. */
  private async acquireCamera(): Promise<boolean> {
    if (!this.video) {
      return false;
    }
    try {
      this.video.srcObject = await this.camera.start();
      await this.video.play();
      writeStored(CAMERA_USED_KEY, 'true');
      return true;
    } catch {
      writeStored(CAMERA_USED_KEY, null);
      this.phase.set('idle');
      return false;
    }
  }
}
