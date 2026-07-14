import { Component, ElementRef, inject, OnDestroy, viewChild } from '@angular/core';
import { Button } from 'primeng/button';
import { CameraService } from '../../services/camera.service';
import { DartSocketService } from '../../services/dart-socket.service';
import { ThrowCaptureService } from '../../services/throw-capture.service';

@Component({
  selector: 'app-capture',
  imports: [Button],
  templateUrl: './capture.component.html',
  styleUrl: './capture.component.scss',
})
export class CaptureComponent implements OnDestroy {
  private readonly camera = inject(CameraService);
  private readonly socket = inject(DartSocketService);
  private readonly capture = inject(ThrowCaptureService);

  private readonly videoRef = viewChild.required<ElementRef<HTMLVideoElement>>('video');
  private readonly diffCanvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('diffCanvas');
  private readonly captureCanvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('captureCanvas');

  readonly cameraStatus = this.camera.status;
  readonly cameraError = this.camera.error;
  readonly connectionStatus = this.socket.connectionStatus;
  readonly displayStatus = this.capture.displayStatus;
  readonly statusLabel = this.capture.statusLabel;

  async start(): Promise<void> {
    await this.capture.start(
      this.videoRef().nativeElement,
      this.diffCanvasRef().nativeElement,
      this.captureCanvasRef().nativeElement,
    );
  }

  stop(): void {
    this.capture.stop();
  }

  ngOnDestroy(): void {
    this.stop();
  }
}
