import { Injectable, signal } from '@angular/core';
import {CameraStatus} from "../models/camera-status";

const CAPTURE_WIDTH = 1280;
const CAPTURE_HEIGHT = 720;

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
        video: {
          facingMode: 'environment',
          width: { ideal: CAPTURE_WIDTH },
          height: { ideal: CAPTURE_HEIGHT },
        },
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

  /**
   * Point a (freshly mounted) video element at the already-running stream. Used
   * when returning to the game screen after navigating away: the stream outlives
   * the component, so the new `<video>` just needs to be rewired to it rather
   * than re-requesting camera access.
   */
  attachTo(video: HTMLVideoElement): void {
    if (this.stream) {
      video.srcObject = this.stream;
    }
  }

  stop(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.status.set('idle');
  }
}
