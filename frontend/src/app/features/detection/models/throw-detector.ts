import { ThrowTriggerDto } from '../dto/throw-trigger.dto';
import { TriggerSampleDto } from '../dto/trigger-sample.dto';
import { TriggerMoment, TriggerSnapshotDto } from '../dto/trigger-snapshot.dto';

export type ThrowDetectorState = 'idle' | 'motion' | 'settling';

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
// 4. *Timeout.* If a fired throw does not settle within MAX_MOTION_FRAMES, the
//    baseline starts following the motion, so the capture waits for a calm frame.
const BLOCK_SIZE = 10; // cell edge in diff pixels → 16×9 grid at 160×90
const BLOCK_MIN_CHANGED = 5; // changed pixels for a cell to count as a cluster
const MAX_THROW_BLOCKS = 48; // above this the change is global, not a dart
const ARM_BLOCK_EXCESS = 1; // cells over the baseline that arm a throw (small = sensitive)
const SETTLE_BLOCK_MARGIN = 1; // back to within this of the baseline counts as still
const AMBIENT_ALPHA = 0.05; // baseline adaptation rate (small = slow)

const SETTLE_FRAMES_REQUIRED = 3;
// At ~16 fps (PROCESS_INTERVAL_MS) roughly 1.5 s of motion before the baseline
// starts adapting to it.
const MAX_MOTION_FRAMES = 25;
// Pause briefly after a capture so the retreating hand does not re-trigger and
// the result has time to show.
const COOLDOWN_FRAMES = 5;
// Processed frames kept for the timeline sent with a capture, about 2.4 s.
const TIMELINE_FRAMES = 40;

interface Sample {
  readonly t: number; // ms, performance clock
  readonly state: ThrowDetectorState;
  readonly activeBlocks: number;
  readonly ambientBlocks: number;
  readonly cells: readonly number[];
}

interface Snapshot {
  readonly t: number; // ms, performance clock
  readonly luma: Uint8ClampedArray;
  readonly changed: Uint8Array; // 1 where the pixel changed
}

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
  private activeBlocks = 0;
  private activeCells: number[] = [];
  private history: Sample[] = [];
  private frameTime = 0; // ms, performance clock, of the frame being processed
  private snapshots = new Map<TriggerMoment, Snapshot>();
  private readonly changed: Uint8Array;
  // Bounding box of this frame's active cells, in cells.
  private spanCols = 0;
  private spanRows = 0;

  // The running episode, from arming to capture.
  private peakBlocks = 0;
  private peakExcess = 0;
  private peakSpanCols = 0;
  private peakSpanRows = 0;
  private trigger: ThrowTriggerDto | null = null;

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
    this.changed = new Uint8Array(width * height);
  }

  getState(): ThrowDetectorState {
    return this.state;
  }

  /** What the episode behind the most recent capture looked like. */
  lastTrigger(): ThrowTriggerDto | null {
    return this.trigger;
  }

  /**
   * Verarbeitet einen neuen Graustufen-Frame.
   * @returns true genau in dem Frame, in dem sich der Wurf als abgeschlossen erwiesen hat.
   */
  processFrame(frame: Uint8ClampedArray): boolean {
    if (!this.previousFrame) {
      this.previousFrame = frame;
      this.activeBlocks = 0;
      return false;
    }

    this.analyseFrame(this.previousFrame, frame);
    this.previousFrame = frame;

    // Erste echte Messung als Baseline setzen, damit ein anfängliches Wackeln
    // nicht sofort als Ausschlag zählt.
    if (!this.ambientPrimed) {
      this.ambientBlocks = this.activeBlocks;
      this.ambientPrimed = true;
    }

    this.frameTime = performance.now();
    const captured = this.step();
    this.recordSample();
    if (captured && this.trigger) {
      this.trigger = { ...this.trigger, timeline: this.timeline() };
    }
    return captured;
  }

  private step(): boolean {
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
    this.activeBlocks = 0;
    this.ambientBlocks = 0;
    this.ambientPrimed = false;
    this.trigger = null;
    this.history = [];
    this.resetCycle();
  }

  private stepIdle(): boolean {
    // A *new localized cluster* over the steady level is a throw candidate. A
    // global disturbance (person, lighting, wobble surge — too many cells) or a
    // quiet frame instead feeds the baseline, so continuous wobble never floods.
    const excess = this.activeBlocks - this.ambientBlocks;
    const localizedThrow = excess >= ARM_BLOCK_EXCESS && this.activeBlocks <= MAX_THROW_BLOCKS;
    if (localizedThrow) {
      this.takeSnapshot('arm');
      this.state = 'motion';
      this.motionFrames = 0;
      this.trackEpisode();
      return false;
    }
    this.updateAmbient();
    return false;
  }

  private stepMotion(): boolean {
    this.motionFrames++;
    this.trackEpisode();
    if (this.isStill()) {
      this.state = 'settling';
      this.stableFrameCount = 1;
    }
    return false;
  }

  private stepSettling(): boolean {
    this.motionFrames++;
    this.trackEpisode();
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
    return false;
  }

  /** Fold this frame into the episode; past the timeout the baseline follows the motion. */
  private trackEpisode(): void {
    if (this.motionFrames >= MAX_MOTION_FRAMES) {
      this.updateAmbient();
    }

    this.peakExcess = Math.max(this.peakExcess, this.activeBlocks - this.ambientBlocks);
    if (this.activeBlocks > this.peakBlocks) {
      this.takeSnapshot('peak');
      this.peakBlocks = this.activeBlocks;
      this.peakSpanCols = this.spanCols;
      this.peakSpanRows = this.spanRows;
    }
  }

  /** The localized change has returned to the steady (wobble/light) level. */
  private isStill(): boolean {
    return this.activeBlocks <= this.ambientBlocks + SETTLE_BLOCK_MARGIN;
  }

  private capture(): boolean {
    this.takeSnapshot('capture');
    this.trigger = {
      peakBlocks: this.peakBlocks,
      peakExcess: Math.round(this.peakExcess * 100) / 100,
      spanCols: this.peakSpanCols,
      spanRows: this.peakSpanRows,
      frames: this.motionFrames,
      timedOut: this.motionFrames >= MAX_MOTION_FRAMES,
      gridCols: this.columns,
      gridRows: this.rows,
      timeline: [],
      snapshots: this.encodedSnapshots(),
    };
    // A baseline raised by a long episode would otherwise mask the next throw.
    this.ambientBlocks = Math.min(this.ambientBlocks, this.activeBlocks);
    this.cooldownFrames = COOLDOWN_FRAMES;
    this.resetCycle();
    return true;
  }

  /** Append this frame to the rolling history, in the state it left the detector in. */
  private recordSample(): void {
    this.history.push({
      t: this.frameTime,
      state: this.state,
      activeBlocks: this.activeBlocks,
      ambientBlocks: this.ambientBlocks,
      cells: this.activeCells,
    });
    if (this.history.length > TIMELINE_FRAMES) {
      this.history.shift();
    }
  }

  /** Keep this frame and its change mask as the given moment of the episode. */
  private takeSnapshot(moment: TriggerMoment): void {
    if (!this.previousFrame) {
      return;
    }
    this.snapshots.set(moment, {
      t: this.frameTime,
      luma: this.previousFrame.slice(),
      changed: this.changed.slice(),
    });
  }

  /** The episode's snapshots, times relative to the capturing frame. */
  private encodedSnapshots(): TriggerSnapshotDto[] {
    const end = this.snapshots.get('capture')?.t ?? 0;
    return [...this.snapshots].map(([moment, { t, luma, changed }]) => ({
      moment,
      tMs: Math.round(t - end),
      width: this.width,
      height: this.height,
      luma: toBase64(luma),
      changed: toBase64(packBits(changed)),
    }));
  }

  /** The history with times relative to the capturing frame. */
  private timeline(): TriggerSampleDto[] {
    const end = this.history[this.history.length - 1]?.t ?? 0;
    return this.history.map(({ t, state, activeBlocks, ambientBlocks, cells }) => ({
      tMs: Math.round(t - end),
      state,
      activeBlocks,
      ambientBlocks: Math.round(ambientBlocks * 100) / 100,
      cells,
    }));
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
    this.peakBlocks = 0;
    this.peakExcess = 0;
    this.peakSpanCols = 0;
    this.peakSpanRows = 0;
    this.snapshots.clear();
  }

  /**
   * Vergleicht zwei Frames: füllt `activeBlocks` (Rasterzellen mit mindestens
   * BLOCK_MIN_CHANGED Pixeln, deren Graustufe sich um mehr als PIXEL_DELTA
   * geändert hat).
   */
  private analyseFrame(a: Uint8ClampedArray, b: Uint8ClampedArray): void {
    this.blockCounts.fill(0);
    let index = 0;
    for (let y = 0; y < this.height; y++) {
      const blockRow = Math.floor(y / BLOCK_SIZE) * this.columns;
      for (let x = 0; x < this.width; x++, index++) {
        const isChanged = Math.abs(a[index] - b[index]) > PIXEL_DELTA;
        this.changed[index] = isChanged ? 1 : 0;
        if (isChanged) {
          this.blockCounts[blockRow + Math.floor(x / BLOCK_SIZE)]++;
        }
      }
    }

    let active = 0;
    const cells: number[] = [];
    let minCol = this.columns;
    let maxCol = -1;
    let minRow = this.rows;
    let maxRow = -1;
    for (let i = 0; i < this.blockCounts.length; i++) {
      if (this.blockCounts[i] >= BLOCK_MIN_CHANGED) {
        active++;
        cells.push(i);
        const col = i % this.columns;
        const row = Math.floor(i / this.columns);
        minCol = Math.min(minCol, col);
        maxCol = Math.max(maxCol, col);
        minRow = Math.min(minRow, row);
        maxRow = Math.max(maxRow, row);
      }
    }

    this.activeBlocks = active;
    this.activeCells = cells;
    this.spanCols = Math.max(0, maxCol - minCol + 1);
    this.spanRows = Math.max(0, maxRow - minRow + 1);
  }
}

/** One bit per entry, most significant bit first; a partial last byte is zero-padded. */
function packBits(values: Uint8Array): Uint8Array {
  const packed = new Uint8Array(Math.ceil(values.length / 8));
  for (let i = 0; i < values.length; i++) {
    if (values[i]) {
      packed[i >> 3] |= 0x80 >> (i & 7);
    }
  }
  return packed;
}

function toBase64(bytes: Uint8Array | Uint8ClampedArray): string {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}
