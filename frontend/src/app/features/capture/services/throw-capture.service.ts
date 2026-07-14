import { Injectable, inject, NgZone, signal } from '@angular/core';
import { DisplayStatus } from '../models/types';
import { ThrowDetector } from '../models/throw-detector';
import { CameraService } from './camera.service';
import { DartSocketService } from './dart-socket.service';

const DIFF_WIDTH = 160;
const DIFF_HEIGHT = 90;
const PROCESS_INTERVAL_MS = 100;
const JPEG_QUALITY = 0.85;
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
 * Orchestriert die komplette Wurf-Erkennungs-Pipeline: Kamera-Frames einlesen,
 * per ThrowDetector auf Bewegung/Stabilisierung prüfen und bei Trigger ein
 * JPEG-Standbild über den DartSocketService versenden.
 */
@Injectable({ providedIn: 'root' })
export class ThrowCaptureService {
  private readonly camera = inject(CameraService);
  private readonly socket = inject(DartSocketService);
  private readonly zone = inject(NgZone);

  readonly displayStatus = signal<DisplayStatus>('idle');
  readonly statusLabel = signal(STATUS_LABELS.idle);

  private readonly detector = new ThrowDetector();
  private animationFrameId: number | null = null;
  private lastProcessedAt = 0;
  private sentDisplayTimeoutId: ReturnType<typeof setTimeout> | null = null;

  private video?: HTMLVideoElement;
  private diffCanvas?: HTMLCanvasElement;
  private captureCanvas?: HTMLCanvasElement;

  async start(
    video: HTMLVideoElement,
    diffCanvas: HTMLCanvasElement,
    captureCanvas: HTMLCanvasElement,
  ): Promise<void> {
    this.video = video;
    this.diffCanvas = diffCanvas;
    this.captureCanvas = captureCanvas;

    const stream = await this.camera.start();
    video.srcObject = stream;
    await video.play();

    this.socket.connect();
    this.detector.reset();
    this.zone.runOutsideAngular(() => this.scheduleNextFrame());
  }

  stop(): void {
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
    if (this.sentDisplayTimeoutId !== null) {
      clearTimeout(this.sentDisplayTimeoutId);
      this.sentDisplayTimeoutId = null;
    }
    this.camera.stop();
    this.socket.disconnect();
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

    const diffContext = this.diffCanvas!.getContext('2d');
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

  private captureAndSendFrame(video: HTMLVideoElement): void {
    const captureCanvas = this.captureCanvas!;
    captureCanvas.width = video.videoWidth;
    captureCanvas.height = video.videoHeight;

    const context = captureCanvas.getContext('2d');
    if (!context) {
      return;
    }
    context.drawImage(video, 0, 0);

    captureCanvas.toBlob(
      (blob) => {
        if (blob) {
          this.socket.sendFrame(blob);
        }
      },
      'image/jpeg',
      JPEG_QUALITY,
    );

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
