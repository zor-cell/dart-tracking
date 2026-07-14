import { Injectable, signal } from '@angular/core';
import { CameraStatus } from '../models/types';

@Injectable({ providedIn: 'root' })
export class CameraService {
  readonly status = signal<CameraStatus>('idle');
  readonly error = signal<string | null>(null);

  private stream: MediaStream | null = null;

  async start(): Promise<MediaStream> {
    this.status.set('starting');
    this.error.set(null);

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false,
      });
      this.status.set('active');
      return this.stream;
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Kamerazugriff fehlgeschlagen');
      this.status.set('error');
      throw err;
    }
  }

  stop(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.status.set('idle');
  }
}
