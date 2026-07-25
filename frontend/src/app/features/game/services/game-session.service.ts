import { Injectable, effect, inject, signal } from '@angular/core';
import { CalibrationService } from '../../calibration/services/calibration.service';
import { CameraService } from '../../camera/services/camera.service';
import { FrameDiffService } from '../../detection/services/frame-diff.service';
import { SocketService } from '../../../core/socket/services/socket.service';
import { CameraPhase } from '../models/camera-phase';
import { GameService } from './game.service';

// Persisted so a full page refresh — which wipes the stream, socket and every
// signal — can tell whether a live camera session was in progress and resume it.
const PHASE_KEY = 'dart-tracking.cameraPhase';

/**
 * Owns the live camera session (phase + the wiring of camera, socket and the
 * detection loop). It is a singleton, so the session survives route changes: the
 * game view hands it its `<video>`/canvas elements on mount (`attachView`) and
 * merely pauses the loop on unmount (`detachView`) — the stream and socket stay
 * up, so returning to the game screen is instant. Full teardown happens only on
 * `endSession` ("Spiel beenden").
 *
 * A page refresh is the other case: everything client-side is gone, but the
 * server keeps the game, calibration and reference frame keyed by game id, so the
 * session reconnects the socket, restarts the camera and resumes tracking.
 */
@Injectable({ providedIn: 'root' })
export class GameSessionService {
  private readonly camera = inject(CameraService);
  private readonly socket = inject(SocketService);
  private readonly calibration = inject(CalibrationService);
  private readonly throwCapture = inject(FrameDiffService);
  private readonly game = inject(GameService);

  readonly phase = signal<CameraPhase>('idle');
  // Re-exposed for the view: the last camera-access error, if any.
  readonly cameraError = this.camera.error;

  // The current view's elements, set by the mounted game component. Undefined
  // while no game view is on screen.
  private video?: HTMLVideoElement;
  private diffCanvas?: HTMLCanvasElement;
  private captureCanvas?: HTMLCanvasElement;

  // The phase from before a refresh, captured once at construction. Consumed on
  // the first view attach to drive a resume, then cleared.
  private persistedPhase = localStorage.getItem(PHASE_KEY) as CameraPhase | null;

  constructor() {
    // Calibration confirmed while on the calibrate step → start tracking.
    effect(() => {
      if (this.calibration.status() === 'success' && this.phase() === 'calibrating') {
        this.startTracking();
      }
    });

    // Mirror the live phase into storage so a refresh can resume from it.
    effect(() => {
      const phase = this.phase();
      if (phase === 'idle') {
        localStorage.removeItem(PHASE_KEY);
      } else {
        localStorage.setItem(PHASE_KEY, phase);
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
      // Returning mid-session (navigation): the stream and socket are still up,
      // so just point this fresh view at the running stream and resume the loop.
      this.camera.attachTo(video);
      void video.play().catch(() => {});
      if (this.phase() === 'tracking') {
        this.runDetectionLoop();
      }
      return;
    }

    void this.bootstrap();
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
    const gameId = this.game.peekGameId();
    if (!gameId || !(await this.acquireCamera())) {
      return;
    }
    this.socket.connect(gameId);
    this.calibration.reset();
    this.phase.set('calibrating');
  }

  /** Capture the current frame for board calibration. */
  async calibrate(): Promise<void> {
    if (this.video && this.captureCanvas) {
      await this.calibration.calibrate(this.video, this.captureCanvas);
    }
  }

  /** End the game: full teardown of the live session. */
  endSession(): void {
    this.throwCapture.stopDetectionLoop();
    this.camera.stop();
    this.socket.disconnect();
    this.calibration.reset();
    this.phase.set('idle');
  }

  /** Load the game (after a refresh) and resume the camera session if one was
   * running. Runs once, on the first view attach of this page load. */
  private async bootstrap(): Promise<void> {
    const target = this.persistedPhase;
    this.persistedPhase = null;

    if (!(await this.game.ensureRestored())) {
      return; // no game, or the server no longer knows it → stay idle
    }
    if (target === 'tracking' || target === 'calibrating') {
      await this.resume(target);
    }
  }

  /** Reconnect the socket and restart the camera after a refresh, landing in the
   * phase the session was in. Tracking trusts the server-side calibration; a
   * moved camera is one "Neu kalibrieren" tap away. */
  private async resume(target: CameraPhase): Promise<void> {
    const gameId = this.game.peekGameId();
    if (!gameId || !(await this.acquireCamera())) {
      return;
    }
    this.socket.connect(gameId);
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
      // Stop first: a re-attach must not leave a second loop running.
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
