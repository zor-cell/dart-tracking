import { Injectable, signal } from '@angular/core';
import { CameraStatus } from '../models/types';

/**
 * Requested capture resolution. Asked for explicitly rather than taking
 * whatever the device defaults to, so that the frames the server sees are the
 * same size regardless of phone — otherwise detection is tuned against one
 * resolution and run against another. Kept in sync with CAPTURE_MAX_EDGE in
 * backend/scripts/check_calibration.py, which replays test photos through the
 * same downscale.
 *
 * These are `ideal`, not `exact`: a camera that cannot deliver them picks the
 * nearest it can rather than failing outright, and portrait sensors may hand
 * back the dimensions swapped.
 */
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

  stop(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.status.set('idle');
  }
}
