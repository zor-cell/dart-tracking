import { Injectable, inject, NgZone, signal } from '@angular/core';
import { ThrowDetector, ThrowDetectorDiagnostics } from '../models/throw-detector';
import { captureFrameAsJpeg } from '../../camera/models/frame-capture';
import { DetectionService } from './detection.service';
import {DisplayStatus} from "../models/frame-diff-status";

const DIFF_WIDTH = 160;
const DIFF_HEIGHT = 90;
// Faster than the eye needs, but a thrown dart is only in shot for a frame or
// two — sampling often makes sure that transient is not missed (recall first).
const PROCESS_INTERVAL_MS = 60;
const SENT_DISPLAY_DURATION_MS = 800;
// The debug numbers refresh far slower than the loop runs, so they stay readable
// and change detection stays cheap; the mask canvas is drawn every frame.
const DEBUG_EMIT_INTERVAL_MS = 150;
// The peak holds then decays, so a throw's spike lingers long enough to read.
const PEAK_DECAY = 0.9;

// ITU-R BT.601 Luma-Gewichte (wahrgenommene Helligkeit pro Farbkanal)
const RED_LUMA_WEIGHT = 0.299;
const GREEN_LUMA_WEIGHT = 0.587;
const BLUE_LUMA_WEIGHT = 0.114;

const STATUS_LABELS: Record<DisplayStatus, string> = {
  idle: 'Bereit',
  motion: 'Bewegung erkannt',
  settling: 'Wird stabilisiert…',
  sent: 'Frame gesendet',
  paused: 'Tracking pausiert',
};

/**
 * Snapshot for the on-screen debug panel. The detector's own numbers are kept
 * whole (`diagnostics`) rather than copied field by field; this service only
 * adds what it owns and the detector cannot know: the loop's high-water mark,
 * the capture tally, and the display-only `'sent'` state.
 */
export interface DetectionDebug {
  readonly diagnostics: ThrowDetectorDiagnostics;
  readonly displayState: DisplayStatus; // detector state plus the transient 'sent'
  readonly peakFraction: number; // recent high-water mark, held then decayed
  // Recent high-water mark of active blocks, held then decayed. The key
  // diagnostic: a dart is a one-frame blip the throttled panel would otherwise
  // miss — if a throw shows peakBlocks 0, the front-end signal was too weak
  // (dart too faint / fell between samples); if ≥ 1 but nothing sent, it is the
  // trigger logic, not the signal.
  readonly peakBlocks: number;
  readonly captureCount: number;
}

const INITIAL_DEBUG: DetectionDebug = {
  diagnostics: {
    state: 'idle',
    changedFraction: 0,
    activeBlocks: 0,
    ambientBlocks: 0,
  },
  displayState: 'idle',
  peakFraction: 0,
  peakBlocks: 0,
  captureCount: 0,
};

/**
 * Continuous frame-diff detection loop: reads an already-active video preview,
 * checks per frame via ThrowDetector for motion/settling, and hands the captured
 * JPEG to DetectionService once a throw is judged complete.
 *
 * Assumes the camera and socket are already up (see CameraService /
 * SocketService) — those outlive this loop, since they're also used for the
 * calibration step that precedes it.
 *
 * When a debug canvas is attached (see `setDebugCanvas`), it also paints the
 * change mask the detector works on and exposes live numbers via `debug`, so a
 * throw that fails to trigger can be watched and the thresholds tuned.
 */
@Injectable({ providedIn: 'root' })
export class FrameDiffService {
  private readonly detection = inject(DetectionService);
  private readonly zone = inject(NgZone);

  readonly displayStatus = signal<DisplayStatus>('idle');
  readonly statusLabel = signal(STATUS_LABELS.idle);
  readonly debug = signal<DetectionDebug>(INITIAL_DEBUG);

  private readonly detector = new ThrowDetector(DIFF_WIDTH, DIFF_HEIGHT);
  private animationFrameId: number | null = null;
  private lastProcessedAt = 0;
  private sentDisplayTimeoutId: ReturnType<typeof setTimeout> | null = null;

  private video?: HTMLVideoElement;
  private diffContext?: CanvasRenderingContext2D;
  private captureCanvas?: HTMLCanvasElement;

  private debugCanvas: HTMLCanvasElement | null = null;
  private debugContext: CanvasRenderingContext2D | null = null;
  private mask?: Uint8ClampedArray;
  private maskImage?: ImageData;
  // The mask is built at diff resolution here, then scaled onto the full-size
  // overlay with the video's cover geometry.
  private maskSource?: CanvasRenderingContext2D;
  private peakFraction = 0;
  private peakBlocks = 0;
  private captureCount = 0;
  private lastDebugEmitAt = 0;

  startDetectionLoop(
    video: HTMLVideoElement,
    diffCanvas: HTMLCanvasElement,
    captureCanvas: HTMLCanvasElement,
  ): void {
    this.video = video;
    this.diffContext = diffCanvas.getContext('2d', { willReadFrequently: true }) ?? undefined;
    this.captureCanvas = captureCanvas;

    this.detector.reset();
    this.peakFraction = 0;
    this.peakBlocks = 0;
    this.captureCount = 0;
    this.setDisplayStatus('idle');
    this.zone.runOutsideAngular(() => this.scheduleNextFrame());
  }

  stopDetectionLoop(): void {
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
    if (this.sentDisplayTimeoutId !== null) {
      clearTimeout(this.sentDisplayTimeoutId);
      this.sentDisplayTimeoutId = null;
    }
    this.setDisplayStatus('idle');
  }

  /**
   * Attach (or detach with null) the full-size canvas the change mask is painted
   * onto — an overlay over the video, mapped with the same cover geometry as the
   * board overlay so the changes sit where they are in the picture.
   */
  setDebugCanvas(canvas: HTMLCanvasElement | null): void {
    this.debugCanvas = canvas;
    this.debugContext = canvas?.getContext('2d') ?? null;
    if (!canvas) {
      return;
    }
    this.mask ??= new Uint8ClampedArray(DIFF_WIDTH * DIFF_HEIGHT);
    this.maskImage ??= new ImageData(DIFF_WIDTH, DIFF_HEIGHT);
    if (!this.maskSource) {
      const source = document.createElement('canvas');
      source.width = DIFF_WIDTH;
      source.height = DIFF_HEIGHT;
      this.maskSource = source.getContext('2d') ?? undefined;
    }
  }

  private scheduleNextFrame(): void {
    this.animationFrameId = requestAnimationFrame((timestamp) => this.onAnimationFrame(timestamp));
  }

  private onAnimationFrame(timestamp: number): void {
    if (timestamp - this.lastProcessedAt >= PROCESS_INTERVAL_MS) {
      this.lastProcessedAt = timestamp;
      this.processFrame(timestamp);
    }
    this.scheduleNextFrame();
  }

  private processFrame(timestamp: number): void {
    const video = this.video!;
    if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      return;
    }

    const diffContext = this.diffContext;
    if (!diffContext) {
      return;
    }

    diffContext.drawImage(video, 0, 0, DIFF_WIDTH, DIFF_HEIGHT);
    const imageData = diffContext.getImageData(0, 0, DIFF_WIDTH, DIFF_HEIGHT);
    const grayscale = toGrayscale(imageData.data);

    const debugOn = this.debugContext !== null;
    const captured = this.detector.processFrame(grayscale, debugOn ? this.mask : undefined);
    // The detector keeps running while the visit is closed, so it stays in step
    // with the picture; only the frame is held back.
    const sending = captured && this.detection.acceptsThrows();
    this.setDisplayStatus(sending ? 'sent' : this.restingStatus());

    if (sending) {
      this.captureCount++;
      this.captureAndSendFrame(video);
    }

    if (debugOn) {
      this.renderDebug(timestamp);
    }
  }

  private async captureAndSendFrame(video: HTMLVideoElement): Promise<void> {
    const frame = await captureFrameAsJpeg(video, this.captureCanvas!);
    await this.detection.submitFrame(frame);

    if (this.sentDisplayTimeoutId !== null) {
      clearTimeout(this.sentDisplayTimeoutId);
    }
    this.sentDisplayTimeoutId = setTimeout(() => {
      this.setDisplayStatus(this.restingStatus());
    }, SENT_DISPLAY_DURATION_MS);
  }

  /** What to show while no frame is going out. */
  private restingStatus(): DisplayStatus {
    return this.detection.acceptsThrows() ? this.detector.getState() : 'paused';
  }

  /** Paint the change mask (every frame) and emit throttled numbers. */
  private renderDebug(timestamp: number): void {
    const diagnostics = this.detector.getDiagnostics();
    this.peakFraction = Math.max(diagnostics.changedFraction, this.peakFraction * PEAK_DECAY);
    this.peakBlocks = Math.max(diagnostics.activeBlocks, this.peakBlocks * PEAK_DECAY);
    this.paintMask();

    if (timestamp - this.lastDebugEmitAt < DEBUG_EMIT_INTERVAL_MS) {
      return;
    }
    this.lastDebugEmitAt = timestamp;
    this.debug.set({
      diagnostics,
      displayState: this.displayStatus(),
      peakFraction: this.peakFraction,
      peakBlocks: this.peakBlocks,
      captureCount: this.captureCount,
    });
  }

  private paintMask(): void {
    const canvas = this.debugCanvas;
    const context = this.debugContext;
    const source = this.maskSource;
    const mask = this.mask;
    const image = this.maskImage;
    const video = this.video;
    if (!canvas || !context || !source || !mask || !image || !video) {
      return;
    }
    if (!video.videoWidth || !video.videoHeight) {
      return;
    }

    // Changed pixels bright green, everything else transparent, so the dimmed
    // video shows through and a dart cluster pops.
    const rgba = image.data;
    for (let i = 0; i < mask.length; i++) {
      const offset = i * 4;
      const on = mask[i] !== 0;
      rgba[offset] = 57;
      rgba[offset + 1] = 255;
      rgba[offset + 2] = 20;
      rgba[offset + 3] = on ? 255 : 0;
    }
    source.putImageData(image, 0, 0);

    // Back the canvas at device resolution, then place the diff-resolution mask
    // onto the video with object-fit: cover geometry (fill, centre, crop the
    // overflow) — the same mapping the board overlay uses.
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    context.imageSmoothingEnabled = false; // keep the diff pixels crisp

    const scale = Math.max(width / video.videoWidth, height / video.videoHeight);
    const drawWidth = video.videoWidth * scale;
    const drawHeight = video.videoHeight * scale;
    const offsetX = (width - drawWidth) / 2;
    const offsetY = (height - drawHeight) / 2;
    context.drawImage(
      source.canvas,
      0,
      0,
      DIFF_WIDTH,
      DIFF_HEIGHT,
      offsetX,
      offsetY,
      drawWidth,
      drawHeight,
    );
  }

  private setDisplayStatus(status: DisplayStatus): void {
    this.displayStatus.set(status);
    this.statusLabel.set(STATUS_LABELS[status]);
  }
}

function toGrayscale(rgba: Uint8ClampedArray): Uint8ClampedArray {
  const pixelCount = rgba.length / 4;
  const grayscale = new Uint8ClampedArray(pixelCount);
  for (let i = 0; i < pixelCount; i++) {
    const offset = i * 4;
    grayscale[i] =
      RED_LUMA_WEIGHT * rgba[offset] + GREEN_LUMA_WEIGHT * rgba[offset + 1] + BLUE_LUMA_WEIGHT * rgba[offset + 2];
  }
  return grayscale;
}
