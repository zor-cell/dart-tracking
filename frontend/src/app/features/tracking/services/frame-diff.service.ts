import { Injectable, inject, NgZone, signal } from '@angular/core';
import { DisplayStatus } from '../models/types';
import { ThrowDetector } from '../models/throw-detector';
import { captureFrameAsJpeg } from '../models/frame-capture';
import { SocketService } from './socket.service';

const DIFF_WIDTH = 160;
const DIFF_HEIGHT = 90;
const PROCESS_INTERVAL_MS = 100;
const SENT_DISPLAY_DURATION_MS = 800;

// ITU-R BT.601 Luma-Gewichte (wahrgenommene Helligkeit pro Farbkanal)
const RED_LUMA_WEIGHT = 0.299;
const GREEN_LUMA_WEIGHT = 0.587;
const BLUE_LUMA_WEIGHT = 0.114;

const STATUS_LABELS: Record<DisplayStatus, string> = {
  idle: 'Bereit',
  motion: 'Bewegung erkannt',
  settling: 'Wird stabilisiert…',
  sent: 'Frame gesendet',
};

/**
 * Continuous frame-diff detection loop: reads an already-active video preview,
 * checks per frame via ThrowDetector for motion/settling, and sends a JPEG
 * `throw_frame` once a throw is judged complete.
 *
 * Assumes the camera and socket are already up (see CameraService /
 * DartSocketService) — those outlive this loop, since they're also used for
 * the calibration step that precedes it.
 */
@Injectable({ providedIn: 'root' })
export class FrameDiffService {
  private readonly socket = inject(SocketService);
  private readonly zone = inject(NgZone);

  readonly displayStatus = signal<DisplayStatus>('idle');
  readonly statusLabel = signal(STATUS_LABELS.idle);

  private readonly detector = new ThrowDetector();
  private animationFrameId: number | null = null;
  private lastProcessedAt = 0;
  private sentDisplayTimeoutId: ReturnType<typeof setTimeout> | null = null;

  private video?: HTMLVideoElement;
  private diffContext?: CanvasRenderingContext2D;
  private captureCanvas?: HTMLCanvasElement;

  startDetectionLoop(
    video: HTMLVideoElement,
    diffCanvas: HTMLCanvasElement,
    captureCanvas: HTMLCanvasElement,
  ): void {
    this.video = video;
    this.diffContext = diffCanvas.getContext('2d', { willReadFrequently: true }) ?? undefined;
    this.captureCanvas = captureCanvas;

    this.detector.reset();
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

  private scheduleNextFrame(): void {
    this.animationFrameId = requestAnimationFrame((timestamp) => this.onAnimationFrame(timestamp));
  }

  private onAnimationFrame(timestamp: number): void {
    if (timestamp - this.lastProcessedAt >= PROCESS_INTERVAL_MS) {
      this.lastProcessedAt = timestamp;
      this.processFrame();
    }
    this.scheduleNextFrame();
  }

  private processFrame(): void {
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

    const captured = this.detector.processFrame(grayscale);
    this.setDisplayStatus(captured ? 'sent' : this.detector.getState());

    if (captured) {
      this.captureAndSendFrame(video);
    }
  }

  private async captureAndSendFrame(video: HTMLVideoElement): Promise<void> {
    const frame = await captureFrameAsJpeg(video, this.captureCanvas!);
    await this.socket.sendFrame('throw_frame', frame);

    if (this.sentDisplayTimeoutId !== null) {
      clearTimeout(this.sentDisplayTimeoutId);
    }
    this.sentDisplayTimeoutId = setTimeout(() => {
      this.setDisplayStatus(this.detector.getState());
    }, SENT_DISPLAY_DURATION_MS);
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
