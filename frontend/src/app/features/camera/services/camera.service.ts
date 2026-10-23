import { Injectable, signal } from '@angular/core';
import {CameraStatus} from "../models/camera-status";
import { cameraErrorMessage } from '../models/camera-error';
import { lockExposure, unlockExposure } from '../models/exposure';
import { applyTorch, hasTorch } from '../models/torch';

const CAPTURE_WIDTH = 1280;
const CAPTURE_HEIGHT = 720;

@Injectable({ providedIn: 'root' })
export class CameraService {
  readonly status = signal<CameraStatus>('idle');
  readonly error = signal<string | null>(null);

  /** Whether the running camera has a light this browser will switch, and
   * whether it is on. Both false while no stream runs. */
  readonly torchSupported = signal(false);
  readonly torchOn = signal(false);

  private stream: MediaStream | null = null;
  private exposureLocked = false;

  /**
   * Start a media stream from the browsers camera
   */
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
      const track = this.videoTrack();
      this.torchSupported.set(track !== null && hasTorch(track));
      this.torchOn.set(false);
      this.status.set('active');
      return this.stream;
    } catch (err) {
      this.error.set(cameraErrorMessage(err));
      this.status.set('error');
      throw err;
    }
  }

  /**
   * Point a (freshly mounted) video element at the already-running stream.
   */
  attachTo(video: HTMLVideoElement): void {
    if (this.stream) {
      video.srcObject = this.stream;
    }
  }

  /** Hold exposure and white balance where they are, so a person or an arm in
   * the picture does not change the brightness of the board between frames. */
  async lockExposure(): Promise<void> {
    const track = this.videoTrack();
    if (track !== null && !this.exposureLocked) {
      this.exposureLocked = await lockExposure(track);
    }
  }

  /**
   * Switch the camera light, where the device has one. Goes out with the stream,
   * so nothing has to be reset on stop. Releases the exposure lock until the
   * next calibration, the light being a different exposure.
   */
  async toggleTorch(): Promise<void> {
    const track = this.videoTrack();
    if (track === null || !this.torchSupported()) {
      return;
    }
    if (this.exposureLocked) {
      await unlockExposure(track);
      this.exposureLocked = false;
    }
    const on = !this.torchOn();
    if (await applyTorch(track, on)) {
      this.torchOn.set(on);
    } else {
      // Advertised but refused: stop offering it rather than showing a switch
      // that does nothing.
      this.torchSupported.set(false);
    }
  }

  /**
   * Stop the running media stream
   */
  stop(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.exposureLocked = false;
    this.torchSupported.set(false);
    this.torchOn.set(false);
    this.status.set('idle');
  }

  private videoTrack(): MediaStreamTrack | null {
    return this.stream?.getVideoTracks()[0] ?? null;
  }
}
