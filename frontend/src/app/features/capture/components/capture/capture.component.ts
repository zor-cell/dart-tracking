import { Component, DestroyRef, ElementRef, inject, NgZone, signal, viewChild } from '@angular/core';
import { Button } from 'primeng/button';
import { ThrowDetector } from '../../models/throw-detector';
import { CameraService } from '../../services/camera.service';
import { DartSocketService } from '../../services/dart-socket.service';
import { DisplayStatus } from '../../models/types';

const DIFF_WIDTH = 160;
const DIFF_HEIGHT = 90;
const PROCESS_INTERVAL_MS = 100;
const JPEG_QUALITY = 0.85;
const SENT_DISPLAY_DURATION_MS = 800;

const STATUS_LABELS: Record<DisplayStatus, string> = {
  idle: 'Bereit',
  motion: 'Bewegung erkannt',
  settling: 'Wird stabilisiert…',
  sent: 'Frame gesendet',
};

@Component({
  selector: 'app-capture',
  imports: [Button],
  templateUrl: './capture.component.html',
  styleUrl: './capture.component.scss',
})
export class CaptureComponent {
  private readonly camera = inject(CameraService);
  private readonly socket = inject(DartSocketService);
  private readonly zone = inject(NgZone);
  private readonly destroyRef = inject(DestroyRef);

  private readonly videoRef = viewChild.required<ElementRef<HTMLVideoElement>>('video');
  private readonly diffCanvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('diffCanvas');
  private readonly captureCanvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('captureCanvas');

  readonly cameraStatus = this.camera.status;
  readonly cameraError = this.camera.error;
  readonly connectionStatus = this.socket.connectionStatus;
  readonly displayStatus = signal<DisplayStatus>('idle');
  readonly statusLabel = signal(STATUS_LABELS.idle);

  private readonly detector = new ThrowDetector();
  private animationFrameId: number | null = null;
  private lastProcessedAt = 0;
  private sentDisplayTimeoutId: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    this.destroyRef.onDestroy(() => this.stop());
  }

  async start(): Promise<void> {
    const stream = await this.camera.start();
    const video = this.videoRef().nativeElement;
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
    const video = this.videoRef().nativeElement;
    if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      return;
    }

    const diffCanvas = this.diffCanvasRef().nativeElement;
    const diffContext = diffCanvas.getContext('2d');
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
    const captureCanvas = this.captureCanvasRef().nativeElement;
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
    this.zone.run(() => {
      this.displayStatus.set(status);
      this.statusLabel.set(STATUS_LABELS[status]);
    });
  }
}

function toGrayscale(rgba: Uint8ClampedArray): Uint8ClampedArray {
  const pixelCount = rgba.length / 4;
  const grayscale = new Uint8ClampedArray(pixelCount);
  for (let i = 0; i < pixelCount; i++) {
    const offset = i * 4;
    grayscale[i] = 0.299 * rgba[offset] + 0.587 * rgba[offset + 1] + 0.114 * rgba[offset + 2];
  }
  return grayscale;
}
