export type ThrowDetectorState = 'idle' | 'motion' | 'settling';

/** Live numbers for the debug view, so a real throw can be watched and tuned. */
export interface ThrowDetectorDiagnostics {
  readonly state: ThrowDetectorState;
  readonly changedFraction: number; // 0..1 — pixels that changed this frame
  readonly motionEnterFraction: number; // threshold to enter "motion"
  readonly settleFraction: number; // below this counts as "still"
}

// Vorläufige Schwellenwerte — mit der Debug-Ansicht am echten Wurf zu justieren.
//
// Bewusst *recall-first*: einen echten Wurf zu verpassen ist schlimmer als ein
// Fehlauslöser (der Server kann eine falsche Antwort noch abfangen). Deshalb
// liegen die Schwellen niedrig.
//
// Kernidee: nicht die *mittlere* Diff übers ganze Bild bewerten (ein Dart sind
// nur ein paar Pixel und geht darin unter, während eine durchs Bild laufende
// Person sie mühelos überschreitet), sondern *wie viele* Pixel sich deutlich
// geändert haben. Die Pro-Pixel-Schwelle PIXEL_DELTA schluckt das Sensorrauschen
// (2–4 Graustufen), sodass die Flächenschwelle sehr niedrig liegen darf, ohne auf
// Rauschen anzuspringen — genau das, was für hohe Trefferquote nötig ist.
const PIXEL_DELTA = 20; // ab so viel Graustufen-Änderung zählt ein Pixel als geändert
const MOTION_ENTER_FRACTION = 0.0015; // ~0.15 % der Pixel → „Bewegung"
const SETTLE_FRACTION = 0.0005; // darunter gilt das Bild als ruhig
const SETTLE_FRAMES_REQUIRED = 3;
// Nach einem Treffer kurz pausieren, damit die zurückweichende Hand nicht sofort
// erneut auslöst und das Ergebnis Zeit zum Anzeigen hat.
const COOLDOWN_FRAMES = 5;

/**
 * Frame-Differenz-Erkennung: idle -> motion -> settling -> (captured event).
 * Erwartet Graustufen-Frames gleicher Größe (heruntergerechnete ImageData.data).
 *
 * Ein feststeckender Pfeil ist in der *aufeinanderfolgenden* Differenz nur
 * während des Fluges/Einschlags sichtbar — sobald er ruht, sind zwei Frames
 * wieder gleich. Der Auslöser fasst also diese kurze Bewegung: idle -> motion
 * (Pfeil fliegt) -> settling (Pfeil steckt, Bild wieder ruhig) -> capture.
 */
export class ThrowDetector {
  private previousFrame: Uint8ClampedArray | null = null;
  private state: ThrowDetectorState = 'idle';
  private stableFrameCount = 0;
  private cooldownFrames = 0;
  private changedFraction = 0;

  getState(): ThrowDetectorState {
    return this.state;
  }

  getDiagnostics(): ThrowDetectorDiagnostics {
    return {
      state: this.state,
      changedFraction: this.changedFraction,
      motionEnterFraction: MOTION_ENTER_FRACTION,
      settleFraction: SETTLE_FRACTION,
    };
  }

  /**
   * Verarbeitet einen neuen Graustufen-Frame.
   * @param mask Optionaler Puffer (Länge = Pixelzahl): wird mit 255 an geänderten
   *   Pixeln gefüllt, sonst 0 — für die Debug-Visualisierung.
   * @returns true genau in dem Frame, in dem sich der Wurf als abgeschlossen erwiesen hat.
   */
  processFrame(frame: Uint8ClampedArray, mask?: Uint8ClampedArray): boolean {
    if (!this.previousFrame) {
      this.previousFrame = frame;
      this.changedFraction = 0;
      mask?.fill(0);
      return false;
    }

    this.changedFraction = this.computeChangedFraction(this.previousFrame, frame, mask);
    this.previousFrame = frame;

    // Während des Cooldowns nichts auswerten, aber die Referenz aktuell halten,
    // damit der Vergleich nach der Pause auf dem neuen Ruhezustand aufsetzt.
    if (this.cooldownFrames > 0) {
      this.cooldownFrames--;
      return false;
    }

    let captured = false;
    const fraction = this.changedFraction;

    switch (this.state) {
      case 'idle':
        if (fraction > MOTION_ENTER_FRACTION) {
          this.state = 'motion';
        }
        break;
      case 'motion':
        if (fraction < SETTLE_FRACTION) {
          this.state = 'settling';
          this.stableFrameCount = 1;
        }
        break;
      case 'settling':
        if (fraction < SETTLE_FRACTION) {
          this.stableFrameCount++;
          if (this.stableFrameCount >= SETTLE_FRAMES_REQUIRED) {
            captured = true;
            this.cooldownFrames = COOLDOWN_FRAMES;
            this.resetCycle();
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
    this.cooldownFrames = 0;
    this.changedFraction = 0;
    this.resetCycle();
  }

  /** Zurück in den Ruhezustand, ohne Referenz oder Cooldown zu berühren. */
  private resetCycle(): void {
    this.state = 'idle';
    this.stableFrameCount = 0;
  }

  /** Anteil der Pixel, deren Graustufe sich um mehr als PIXEL_DELTA geändert hat. */
  private computeChangedFraction(
    a: Uint8ClampedArray,
    b: Uint8ClampedArray,
    mask?: Uint8ClampedArray,
  ): number {
    let changed = 0;
    for (let i = 0; i < a.length; i++) {
      const isChanged = Math.abs(a[i] - b[i]) > PIXEL_DELTA;
      if (isChanged) {
        changed++;
      }
      if (mask) {
        mask[i] = isChanged ? 255 : 0;
      }
    }
    return changed / a.length;
  }
}
