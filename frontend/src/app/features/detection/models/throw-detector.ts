export type ThrowDetectorState = 'idle' | 'motion' | 'settling';

/** Live numbers for the debug view, so a real throw can be watched and tuned. */
export interface ThrowDetectorDiagnostics {
  readonly state: ThrowDetectorState;
  readonly changedFraction: number; // 0..1 — pixels that changed this frame (informational)
  readonly activeBlocks: number; // localized change clusters this frame
  readonly ambientBlocks: number; // steady baseline (wobble/light), subtracted before arming
}

// Per-pixel difference counting as changed, in grey levels. Sensor noise sits
// around 2-4, so this is far above it while still catching a dark dart against a
// dark segment. After this threshold a quiet scene has ~0 changed pixels.
const PIXEL_DELTA = 20;

// --- Recall-first arming ----------------------------------------------------
//
// The one rule that matters: a thrown dart must *always* produce a sent frame. A
// false send is cheap — the backend re-checks every frame and rejects a non-dart
// — but a missed throw is unrecoverable. So the trigger errs heavily toward
// firing.
//
// Key insight (confirmed in the field): a dart adds *very few* changed pixels,
// concentrated in one spot (dark, thin, on a dark board). A person walking
// through changes *many* pixels across the whole frame. The old trigger keyed on
// the pixel *count* crossing ~0.15 % (~22 px) — tuned for motion, but a faint
// dart falls *below* it and was silently dropped. Wrong way round.
//
// So arming keys on *localized clusters*, not on the pixel fraction:
//
// 1. *Block grid.* The frame is split into cells; a cell is "active" when it
//    holds at least BLOCK_MIN_CHANGED changed pixels — i.e. a concentrated
//    cluster, not scattered noise. A dart lights one or two cells; a person or a
//    whole-board wobble lights many.
// 2. *Ambient block baseline.* A wobbling tripod shifts every edge and lights
//    cells continuously; that steady level is tracked as a baseline and
//    subtracted. Arming needs cells *above* the steady level — a *new* cluster.
//    So the dart's spike still fires even while the board shimmers.
// 3. *Arm on the smallest new cluster.* ARM_BLOCK_EXCESS cells over the baseline
//    is enough — deliberately tiny, so a faint dart is caught. Anything larger
//    than MAX_THROW_BLOCKS is a global disturbance (person, lighting, wobble
//    surge): folded into the baseline instead of fired, so it does not flood.
// 4. *Timeout.* If a fired throw never settles (wobble grows mid-throw), it is
//    captured anyway after MAX_MOTION_FRAMES.
const BLOCK_SIZE = 10; // cell edge in diff pixels → 16×9 grid at 160×90
const BLOCK_MIN_CHANGED = 5; // changed pixels for a cell to count as a cluster
const MAX_THROW_BLOCKS = 48; // above this the change is global, not a dart
const ARM_BLOCK_EXCESS = 1; // cells over the baseline that arm a throw (small = sensitive)
const SETTLE_BLOCK_MARGIN = 1; // back to within this of the baseline counts as still
const AMBIENT_ALPHA = 0.05; // baseline adaptation rate (small = slow)

const SETTLE_FRAMES_REQUIRED = 3;
// At ~16 fps (PROCESS_INTERVAL_MS) roughly 1.5 s: if no clean settle happens by
// then, capture anyway (recall safety net).
const MAX_MOTION_FRAMES = 25;
// Pause briefly after a capture so the retreating hand does not re-trigger and
// the result has time to show.
const COOLDOWN_FRAMES = 5;

/**
 * Frame-Differenz-Erkennung: idle -> motion -> settling -> (captured event).
 * Erwartet Graustufen-Frames gleicher Größe (heruntergerechnete ImageData.data).
 *
 * Ein feststeckender Pfeil ist in der *aufeinanderfolgenden* Differenz nur
 * während des Einschlags sichtbar — sobald er ruht, sind zwei Frames wieder
 * gleich. Der Auslöser fasst also diesen kurzen Moment: idle -> motion (ein neuer
 * lokalisierter Cluster erscheint) -> settling (Bild wieder ruhig) -> capture.
 *
 * Ausgelegt auf *Recall*: jeder Wurf muss einen Frame erzeugen; ein Fehlauslöser
 * ist billig (der Server filtert), ein verpasster Wurf nicht. Siehe Konstanten.
 */
export class ThrowDetector {
  private previousFrame: Uint8ClampedArray | null = null;
  private state: ThrowDetectorState = 'idle';
  private stableFrameCount = 0;
  private motionFrames = 0;
  private cooldownFrames = 0;
  private changedFraction = 0;
  private activeBlocks = 0;

  // Steady localized-change level (wobble/light); arming is relative to it.
  private ambientBlocks = 0;
  private ambientPrimed = false;

  private readonly columns: number;
  private readonly rows: number;
  private readonly blockCounts: Int32Array;

  /** @param width @param height Abmessungen der Diff-Frames (z.B. 160×90). */
  constructor(
    private readonly width: number,
    private readonly height: number,
  ) {
    this.columns = Math.ceil(width / BLOCK_SIZE);
    this.rows = Math.ceil(height / BLOCK_SIZE);
    this.blockCounts = new Int32Array(this.columns * this.rows);
  }

  getState(): ThrowDetectorState {
    return this.state;
  }

  getDiagnostics(): ThrowDetectorDiagnostics {
    return {
      state: this.state,
      changedFraction: this.changedFraction,
      activeBlocks: this.activeBlocks,
      ambientBlocks: this.ambientBlocks,
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
      this.activeBlocks = 0;
      mask?.fill(0);
      return false;
    }

    this.analyseFrame(this.previousFrame, frame, mask);
    this.previousFrame = frame;

    // Erste echte Messung als Baseline setzen, damit ein anfängliches Wackeln
    // nicht sofort als Ausschlag zählt.
    if (!this.ambientPrimed) {
      this.ambientBlocks = this.activeBlocks;
      this.ambientPrimed = true;
    }

    // Während des Cooldowns nichts auswerten, aber Referenz und Baseline aktuell
    // halten, damit der Vergleich nach der Pause auf dem neuen Ruhezustand aufsetzt.
    if (this.cooldownFrames > 0) {
      this.cooldownFrames--;
      this.updateAmbient();
      return false;
    }

    switch (this.state) {
      case 'idle':
        return this.stepIdle();
      case 'motion':
        return this.stepMotion();
      case 'settling':
        return this.stepSettling();
    }
  }

  reset(): void {
    this.previousFrame = null;
    this.cooldownFrames = 0;
    this.changedFraction = 0;
    this.activeBlocks = 0;
    this.ambientBlocks = 0;
    this.ambientPrimed = false;
    this.resetCycle();
  }

  private stepIdle(): boolean {
    // A *new localized cluster* over the steady level is a throw candidate. A
    // global disturbance (person, lighting, wobble surge — too many cells) or a
    // quiet frame instead feeds the baseline, so continuous wobble never floods.
    const excess = this.activeBlocks - this.ambientBlocks;
    const localizedThrow = excess >= ARM_BLOCK_EXCESS && this.activeBlocks <= MAX_THROW_BLOCKS;
    if (localizedThrow) {
      this.state = 'motion';
      this.motionFrames = 0;
      return false;
    }
    this.updateAmbient();
    return false;
  }

  private stepMotion(): boolean {
    this.motionFrames++;
    if (this.isStill()) {
      this.state = 'settling';
      this.stableFrameCount = 1;
      return false;
    }
    // Kommt kein Settling zustande (Wackeln hält an), trotzdem erfassen.
    return this.motionFrames >= MAX_MOTION_FRAMES ? this.capture() : false;
  }

  private stepSettling(): boolean {
    this.motionFrames++;
    if (this.isStill()) {
      this.stableFrameCount++;
      if (this.stableFrameCount >= SETTLE_FRAMES_REQUIRED) {
        return this.capture();
      }
      return false;
    }
    // Neue Bewegung während der Stabilisierung -> zurück auf motion, aber das
    // Timeout läuft weiter (motionFrames wird nicht zurückgesetzt).
    this.state = 'motion';
    this.stableFrameCount = 0;
    return this.motionFrames >= MAX_MOTION_FRAMES ? this.capture() : false;
  }

  /** The localized change has returned to the steady (wobble/light) level. */
  private isStill(): boolean {
    return this.activeBlocks <= this.ambientBlocks + SETTLE_BLOCK_MARGIN;
  }

  private capture(): boolean {
    this.cooldownFrames = COOLDOWN_FRAMES;
    this.resetCycle();
    return true;
  }

  /** Baseline träge in Richtung der aktuellen Block-Zahl nachziehen. */
  private updateAmbient(): void {
    this.ambientBlocks += AMBIENT_ALPHA * (this.activeBlocks - this.ambientBlocks);
  }

  /** Zurück in den Ruhezustand, ohne Referenz, Baseline oder Cooldown zu berühren. */
  private resetCycle(): void {
    this.state = 'idle';
    this.stableFrameCount = 0;
    this.motionFrames = 0;
  }

  /**
   * Vergleicht zwei Frames: füllt `changedFraction` (Anteil der Pixel, deren
   * Graustufe sich um mehr als PIXEL_DELTA geändert hat) und `activeBlocks`
   * (Rasterzellen mit mindestens BLOCK_MIN_CHANGED geänderten Pixeln), und
   * schreibt optional die Debug-Maske.
   */
  private analyseFrame(
    a: Uint8ClampedArray,
    b: Uint8ClampedArray,
    mask?: Uint8ClampedArray,
  ): void {
    this.blockCounts.fill(0);
    let changed = 0;
    let index = 0;
    for (let y = 0; y < this.height; y++) {
      const blockRow = Math.floor(y / BLOCK_SIZE) * this.columns;
      for (let x = 0; x < this.width; x++, index++) {
        const isChanged = Math.abs(a[index] - b[index]) > PIXEL_DELTA;
        if (isChanged) {
          changed++;
          this.blockCounts[blockRow + Math.floor(x / BLOCK_SIZE)]++;
        }
        if (mask) {
          mask[index] = isChanged ? 255 : 0;
        }
      }
    }

    let active = 0;
    for (let i = 0; i < this.blockCounts.length; i++) {
      if (this.blockCounts[i] >= BLOCK_MIN_CHANGED) {
        active++;
      }
    }

    this.changedFraction = changed / a.length;
    this.activeBlocks = active;
  }
}
