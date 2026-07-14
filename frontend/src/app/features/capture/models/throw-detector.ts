export type ThrowDetectorState = 'idle' | 'motion' | 'settling';

// Vorläufige Schwellenwerte — Tuning erfolgt später mit echten Testvideos (Phase 3).
const MOTION_THRESHOLD = 12;
const SETTLE_THRESHOLD = 4;
const SETTLE_FRAMES_REQUIRED = 5;

/**
 * Reine Frame-Differenz-Erkennung: idle -> motion -> settling -> (captured event).
 * Erwartet Graustufen-Frames gleicher Größe (z.B. heruntergerechnete ImageData.data).
 */
export class ThrowDetector {
  private previousFrame: Uint8ClampedArray | null = null;
  private state: ThrowDetectorState = 'idle';
  private stableFrameCount = 0;

  getState(): ThrowDetectorState {
    return this.state;
  }

  /**
   * Verarbeitet einen neuen Graustufen-Frame.
   * @returns true genau in dem Frame, in dem sich der Wurf als abgeschlossen erwiesen hat.
   */
  processFrame(frame: Uint8ClampedArray): boolean {
    if (!this.previousFrame) {
      this.previousFrame = frame;
      return false;
    }

    const diff = ThrowDetector.averageAbsoluteDiff(this.previousFrame, frame);
    this.previousFrame = frame;

    let captured = false;

    switch (this.state) {
      case 'idle':
        if (diff > MOTION_THRESHOLD) {
          this.state = 'motion';
        }
        break;
      case 'motion':
        if (diff < SETTLE_THRESHOLD) {
          this.state = 'settling';
          this.stableFrameCount = 1;
        }
        break;
      case 'settling':
        if (diff < SETTLE_THRESHOLD) {
          this.stableFrameCount++;
          if (this.stableFrameCount >= SETTLE_FRAMES_REQUIRED) {
            captured = true;
            this.state = 'idle';
            this.stableFrameCount = 0;
          }
        } else {
          // Neue Bewegung während der Stabilisierung -> zurück auf motion.
          this.state = 'motion';
          this.stableFrameCount = 0;
        }
        break;
    }

    return captured;
  }

  reset(): void {
    this.previousFrame = null;
    this.state = 'idle';
    this.stableFrameCount = 0;
  }

  private static averageAbsoluteDiff(a: Uint8ClampedArray, b: Uint8ClampedArray): number {
    let sum = 0;
    for (let i = 0; i < a.length; i++) {
      sum += Math.abs(a[i] - b[i]);
    }
    return sum / a.length;
  }
}
