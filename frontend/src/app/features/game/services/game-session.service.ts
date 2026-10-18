import { Injectable, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CalibrationService } from '../../calibration/services/calibration.service';
import { CameraService } from '../../camera/services/camera.service';
import { FrameDiffService } from '../../detection/services/frame-diff.service';
import { DeviceRole } from '../../../core/socket/models/device-role';
import { SocketService } from '../../../core/socket/services/socket.service';
import { CameraPhase } from '../models/camera-phase';
import { GameService } from './game.service';

// Kept across a refresh — which wipes the stream, socket and every signal — so
// the session can tell that a live camera was in progress and resume it. In
// sessionStorage, not localStorage: a running camera belongs to this sitting,
// not to the device for good.
const PHASE_KEY = 'dart-tracking.cameraPhase';

/**
 * Owns the live camera session (phase + the wiring of camera and the detection
 * loop). It is a singleton, so the session survives route changes: the game view
 * hands it its `<video>`/canvas elements on mount (`attachView`) and merely
 * pauses the loop on unmount (`detachView`) — the stream stays up, so returning
 * to the game screen is instant. Full teardown happens only on `endSession`
 * ("Spiel verlassen").
 *
 * The socket is deliberately not its business: it belongs to the game, not to
 * the camera, since a device that only keeps score holds one too (`GameService`).
 * This service is what turns *this* device into the one that films the board —
 * which is also why the device's role lives here.
 *
 * A page refresh is the other case: everything client-side is gone, but the
 * server keeps the game, calibration and reference frame keyed by game id, so the
 * session restarts the camera and resumes tracking.
 */
@Injectable({ providedIn: 'root' })
export class GameSessionService {
  private readonly camera = inject(CameraService);
  private readonly calibration = inject(CalibrationService);
  private readonly throwCapture = inject(FrameDiffService);
  private readonly game = inject(GameService);
  private readonly socket = inject(SocketService);

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
  private persistedPhase = sessionStorage.getItem(PHASE_KEY) as CameraPhase | null;

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

    // A recalibration asked for elsewhere: the scoreboard's button, the end of
    // a visit, or joining a game the server holds no calibration for. The server
    // sends it to camera devices only; the phase is what says whether this one
    // has a running picture to answer it with.
    this.socket
      .on('calibration_requested')
      .pipe(takeUntilDestroyed())
      .subscribe(() => {
        if (this.phase() !== 'idle') {
          void this.calibrate();
        }
      });

    // Mirror the live phase into storage so a refresh can resume from it.
    effect(() => {
      const phase = this.phase();
      if (phase === 'idle') {
        sessionStorage.removeItem(PHASE_KEY);
      } else {
        sessionStorage.setItem(PHASE_KEY, phase);
      }
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
    }
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

  /** Refetch the game when the game view initialises (called from its ngOnInit),
   * independent of the DOM, so a full reload restores the state even before the
   * camera elements exist. Stash the phase to resume the camera into; the resume
   * itself happens on the following view attach. Cleared if there is no game. */
  async restore(): Promise<boolean> {
    // No role check: a stored phase can only come from a device that was
    // filming, and the resume waits for the camera elements — which exist only
    // in the camera view.
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
    this.endSession();
    this.game.reset();
  }

  /** Restart the camera after a refresh, landing in the phase the session was
   * in. Tracking trusts the server-side calibration; a moved camera is one "Neu
   * kalibrieren" tap away. */
  private async resume(target: CameraPhase): Promise<void> {
    if (!this.game.peekGameId() || !(await this.acquireCamera())) {
      return;
    }
    this.phase.set(target);
    if (target === 'tracking') {
      this.runDetectionLoop();
    }
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

  /** Point the current video element at a freshly started stream; on denial the
   * session falls back to idle. Returns whether the camera came up. */
  private async acquireCamera(): Promise<boolean> {
    if (!this.video) {
      return false;
    }
    try {
      this.video.srcObject = await this.camera.start();
      await this.video.play();
      return true;
    } catch {
      this.phase.set('idle');
      return false;
    }
  }
}
