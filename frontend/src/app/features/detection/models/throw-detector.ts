export type ThrowDetectorState = 'idle' | 'motion' | 'settling';

/** Live numbers for the debug view, so a real throw can be watched and tuned. */
export interface ThrowDetectorDiagnostics {
  readonly state: ThrowDetectorState;
  readonly changedFraction: number; // 0..1 — pixels that changed this frame
  readonly ambientFraction: number; // rolling baseline: wobble / lighting level
  readonly activeBlocks: number; // coarse-grid cells with strong change
  readonly motionEnterFraction: number; // live arm threshold (ambient + margin)
  readonly settleFraction: number; // live settle threshold (ambient + margin)
}

// Schwellenwerte — mit der Debug-Ansicht am echten Wurf zu justieren.
//
// Bewusst *recall-first*: einen echten Wurf zu verpassen ist schlimmer als ein
// Fehlauslöser (der Server kann eine falsche Antwort noch abfangen). Deshalb
// löst der Trigger im Zweifel lieber aus.
//
// Kernidee: nicht die *mittlere* Diff übers ganze Bild bewerten (ein Dart sind
// nur ein paar Pixel und geht darin unter, während eine durchs Bild laufende
// Person sie mühelos überschreitet), sondern *wie viele* Pixel sich deutlich
// geändert haben. Die Pro-Pixel-Schwelle PIXEL_DELTA schluckt das Sensorrauschen
// (2–4 Graustufen), sodass die Flächenschwelle sehr niedrig liegen darf.
const PIXEL_DELTA = 20; // ab so viel Graustufen-Änderung zählt ein Pixel als geändert

// --- Wackel-Robustheit (Stativ vibriert, Kamera driftet) --------------------
//
// Zwei Bausteine gegen ein wackelndes Stativ, ohne echte Würfe zu verlieren:
//
// 1. *Ambient-Baseline.* Ein wackelndes Stativ verschiebt das ganze Bild um
//    ~1 px, wodurch jede Board-Kante in der Consecutive-Diff aufleuchtet — die
//    absolute Änderungsrate ist dann dauerhaft erhöht. Mit festen Schwellen
//    würde der Detektor entweder dauernd fälschlich auslösen oder (schlimmer)
//    nach echtem Wurf nie mehr *unter* die Settle-Schwelle fallen und den Wurf
//    nie als abgeschlossen erkennen. Stattdessen wird ein gleitender Mittelwert
//    der ruhigen Änderungsrate mitgeführt (das Wackel-/Lichtniveau) und alle
//    Schwellen *relativ* dazu gesetzt. Ausgelöst wird auf den *Ausschlag über*
//    dieses Niveau, ruhig ist das Bild wieder bei Rückkehr *auf* das Niveau — so
//    funktioniert das Settling auch bei Dauer-Wackeln.
//
// 2. *Konzentration.* Wackeln/Licht verteilt die Änderung übers ganze Board,
//    ein einschlagender Pfeil konzentriert sie an einer Stelle. Über ein grobes
//    Raster wird gezählt, in wie vielen Zellen sich stark etwas ändert; ein
//    Ausschlag, der über zu viele Zellen streut, gilt als globale Störung
//    (Wackel-Schub, Lichtwechsel, Person) und fließt in die Baseline statt
//    auszulösen — nur ein *lokalisierter* Ausschlag ist ein Wurf-Kandidat.
//
// 3. *Timeout.* Bleibt trotz allem das Settling aus (Wackeln nimmt mitten im
//    Wurf zu), wird nach MAX_MOTION_FRAMES trotzdem ausgelöst. Recall geht vor:
//    lieber ein zu früher Frame, den der Server verwirft, als ein verlorener.
const BLOCK_SIZE = 10; // Kantenlänge einer Rasterzelle in Diff-Pixeln
const BLOCK_MIN_CHANGED = 8; // ab so vielen geänderten Pixeln gilt eine Zelle als aktiv
const MAX_THROW_BLOCKS = 48; // darüber ist der Ausschlag global (Wackeln), kein Wurf
const AMBIENT_ALPHA = 0.05; // Anpassungsrate der Baseline (klein = träge)

const MOTION_ENTER_MARGIN = 0.0015; // Ausschlag über Baseline → „Bewegung"
const SETTLE_MARGIN = 0.0005; // innerhalb davon über Baseline gilt als ruhig
const SETTLE_FRAMES_REQUIRED = 3;
// Bei ~16 fps (PROCESS_INTERVAL_MS) etwa 1,5 s: kommt bis dahin kein sauberes
// Settling zustande, wird der Wurf trotzdem erfasst (Recall-Sicherheitsnetz).
const MAX_MOTION_FRAMES = 25;
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
 *
 * Alle Schwellen sind relativ zu einer mitgeführten Wackel-/Licht-Baseline und
 * durch einen Konzentrations- und einen Timeout-Test gegen ein wackelndes
 * Stativ abgesichert (siehe Konstanten oben).
 */
export class ThrowDetector {
  private previousFrame: Uint8ClampedArray | null = null;
  private state: ThrowDetectorState = 'idle';
  private stableFrameCount = 0;
  private motionFrames = 0;
  private cooldownFrames = 0;
  private changedFraction = 0;
  private activeBlocks = 0;

  // Gleitendes Wackel-/Licht-Niveau; alle Schwellen liegen relativ dazu.
  private ambient = 0;
  private ambientPrimed = false;

  private readonly columns: number;
  private readonly rows: number;
  private readonly blockCounts: Int32Array;

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
      ambientFraction: this.ambient,
      activeBlocks: this.activeBlocks,
      motionEnterFraction: this.ambient + MOTION_ENTER_MARGIN,
      settleFraction: this.ambient + SETTLE_MARGIN,
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
      this.ambient = this.changedFraction;
      this.ambientPrimed = true;
    }

    // Während des Cooldowns nichts auswerten, aber Referenz und Baseline aktuell
    // halten, damit der Vergleich nach der Pause auf dem neuen Ruhezustand aufsetzt.
    if (this.cooldownFrames > 0) {
      this.cooldownFrames--;
      this.updateAmbient();
      return false;
    }

    const armThreshold = this.ambient + MOTION_ENTER_MARGIN;
    const settleThreshold = this.ambient + SETTLE_MARGIN;

    switch (this.state) {
      case 'idle':
        return this.stepIdle(armThreshold);
      case 'motion':
        return this.stepMotion(settleThreshold);
      case 'settling':
        return this.stepSettling(settleThreshold);
    }
  }

  reset(): void {
    this.previousFrame = null;
    this.cooldownFrames = 0;
    this.changedFraction = 0;
    this.activeBlocks = 0;
    this.ambient = 0;
    this.ambientPrimed = false;
    this.resetCycle();
  }

  private stepIdle(armThreshold: number): boolean {
    // Ein *lokalisierter* Ausschlag über die Baseline ist ein Wurf-Kandidat.
    // Alles andere — ruhiges Bild oder ein über das ganze Board gestreuter
    // Ausschlag (Wackel-Schub, Lichtwechsel) — fließt in die Baseline, statt
    // auszulösen, sodass Dauer-Wackeln den Trigger nicht flutet.
    const spike = this.changedFraction > armThreshold;
    const localized = this.activeBlocks > 0 && this.activeBlocks <= MAX_THROW_BLOCKS;
    if (spike && localized) {
      this.state = 'motion';
      this.motionFrames = 0;
      return false;
    }
    this.updateAmbient();
    return false;
  }

  private stepMotion(settleThreshold: number): boolean {
    this.motionFrames++;
    if (this.changedFraction < settleThreshold) {
      this.state = 'settling';
      this.stableFrameCount = 1;
      return false;
    }
    // Kommt kein Settling zustande (Wackeln hält an), trotzdem erfassen.
    return this.motionFrames >= MAX_MOTION_FRAMES ? this.capture() : false;
  }

  private stepSettling(settleThreshold: number): boolean {
    this.motionFrames++;
    if (this.changedFraction < settleThreshold) {
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

  private capture(): boolean {
    this.cooldownFrames = COOLDOWN_FRAMES;
    this.resetCycle();
    return true;
  }

  /** Baseline träge in Richtung der aktuellen Änderungsrate nachziehen. */
  private updateAmbient(): void {
    this.ambient += AMBIENT_ALPHA * (this.changedFraction - this.ambient);
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
