import { effect, inject, Injectable, signal } from '@angular/core';
import { captureFrameAsJpeg } from '../models/frame-capture';
import { SocketService } from './socket.service';

export type CalibrationStatus = 'idle' | 'pending' | 'success' | 'error';

/**
 * One-shot board calibration: capture the current video frame, send it as a
 * `calibration_frame` and track the `calibration_result` that comes back over
 * the shared socket. The actual board detection is server-side (stub for now
 * — see backend/.../features/tracking/darts.py).
 */
@Injectable({ providedIn: 'root' })
export class CalibrationService {
  private readonly socket = inject(SocketService);

  readonly status = signal<CalibrationStatus>('idle');

  constructor() {
    effect(() => {
      const message = this.socket.lastMessage();
      if (message?.type === 'calibration_result' && this.status() === 'pending') {
        this.status.set(message.success ? 'success' : 'error');
      }
    });
  }

  async calibrate(video: HTMLVideoElement, canvas: HTMLCanvasElement): Promise<void> {
    this.status.set('pending');
    const frame = await captureFrameAsJpeg(video, canvas);
    await this.socket.sendFrame('calibration_frame', frame);
  }

  reset(): void {
    this.status.set('idle');
  }
}
