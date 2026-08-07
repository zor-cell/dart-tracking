import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  ElementRef,
  inject,
  OnDestroy,
  OnInit,
  signal,
  viewChild,
} from '@angular/core';
import {RouterLink} from '@angular/router';
import {Button} from 'primeng/button';
import {OverlayComponent} from '../../../calibration/components/overlay/overlay.component';
import {CalibrationService} from '../../../calibration/services/calibration.service';
import {DetectionService} from '../../../detection/services/detection.service';
import {FrameDiffService} from '../../../detection/services/frame-diff.service';
import {SettingsService} from '../../../settings/services/settings.service';
import {GameService} from '../../services/game.service';
import {GameSessionService} from '../../services/game-session.service';

/** Score keypad layout: four numbers per row, with the bull/miss values down
 * the side column (top two rows have no side key). */
type PadRow = { readonly numbers: number[]; readonly side: number | null };

const PAD_ROWS: readonly PadRow[] = [
  { numbers: [1, 2, 3, 4], side: null },
  { numbers: [5, 6, 7, 8], side: null },
  { numbers: [9, 10, 11, 12], side: 0 },
  { numbers: [13, 14, 15, 16], side: 25 },
  { numbers: [17, 18, 19, 20], side: 50 },
];

@Component({
  selector: 'app-game',
  imports: [RouterLink, Button, OverlayComponent],
  templateUrl: './game.component.html',
  styleUrl: './game.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameComponent implements OnInit, OnDestroy {
  protected readonly game = inject(GameService);
  protected readonly settings = inject(SettingsService);

  private readonly session = inject(GameSessionService);
  private readonly calibration = inject(CalibrationService);
  private readonly throwCapture = inject(FrameDiffService);
  private readonly detection = inject(DetectionService);

  // Optional: these live behind the "game active" gate, so they are absent until
  // the state is (re)loaded — which after a full reload is a few ticks after init.
  private readonly videoRef = viewChild<ElementRef<HTMLVideoElement>>('video');
  private readonly diffCanvasRef = viewChild<ElementRef<HTMLCanvasElement>>('diffCanvas');
  private readonly captureCanvasRef = viewChild<ElementRef<HTMLCanvasElement>>('captureCanvas');
  private readonly detectionDebugCanvasRef = viewChild<ElementRef<HTMLCanvasElement>>('detectionDebugCanvas');

  protected readonly cameraPhase = this.session.phase;
  protected readonly cameraError = this.session.cameraError;
  protected readonly calibrationStatus = this.calibration.status;
  protected readonly calibrationOverlay = this.calibration.overlay;
  protected readonly roundDarts = this.detection.roundDarts;
  protected readonly detectionStatusLabel = this.throwCapture.statusLabel;
  protected readonly detectionFeedback = this.detection.feedbackLabel;
  protected readonly detectionDebug = this.throwCapture.debug;
  protected readonly detectionEvents = this.detection.events;

  // The client debug view (change mask, numbers, event log, sent-frame preview)
  // is on only while tracking and switched on — separate from the server-side
  // detection-image dump (settings.debugDetection).
  protected readonly debugActive = computed(
    () => this.settings.debugClientDetection() && this.cameraPhase() === 'tracking',
  );

  protected readonly padRows = PAD_ROWS;

  protected readonly multiplier = signal<1 | 2 | 3>(1);
  protected readonly multiplierPrefix = computed(() =>
    this.multiplier() === 2 ? 'D' : this.multiplier() === 3 ? 'T' : '',
  );

  // The most recent *finished* visit, tagged with its player — shown as darts
  // next to that player alone, never as a total. The open turn (always the last
  // one) is skipped, so a visit in progress stays in the dart boxes below and
  // only moves up to the scoreboard once play has passed on.
  protected readonly lastThrow = computed(() => {
    const turns = this.game.state()?.turns ?? [];
    for (let index = turns.length - 2; index >= 0; index--) {
      const turn = turns[index];
      if (turn.darts.length > 0) {
        return { playerId: turn.playerId, darts: turn.darts, busted: turn.busted };
      }
    }
    return null;
  });

  protected readonly checkoutSlots = computed<(string | null)[]>(() => {
    const state = this.game.state();
    const remaining = state?.dartsRemaining ?? 0;
    const checkout = state?.checkout ?? null;
    return Array.from({ length: remaining }, (_, index) => checkout?.[index] ?? null);
  });

  constructor() {
    // Attach the change-mask canvas whenever the debug panel is on screen, and
    // detach it the moment it leaves — keeping the loop's debug work off unless
    // someone is watching.
    effect(() => {
      const canvas = this.detectionDebugCanvasRef()?.nativeElement ?? null;
      this.throwCapture.setDebugCanvas(this.settings.debugClientDetection() ? canvas : null);
    });

    // Hand the session this view's camera elements once they exist. They live
    // behind the "game active" gate, so after a full reload — where the state is
    // refetched first — they appear a few ticks after init, not at view init.
    // The session then resumes an ongoing session or the phase from before.
    effect(() => {
      const video = this.videoRef()?.nativeElement;
      const diffCanvas = this.diffCanvasRef()?.nativeElement;
      const captureCanvas = this.captureCanvasRef()?.nativeElement;
      if (video && diffCanvas && captureCanvas) {
        this.session.attachView(video, diffCanvas, captureCanvas);
      }
    });
  }

  ngOnInit(): void {
    // Refetch the game after a full reload so the view — and with it the camera
    // elements — can render; wiring and camera resume then happen on attach.
    void this.session.restore();
  }

  protected startCamera(): Promise<void> {
    return this.session.startCamera();
  }

  protected calibrateBoard(): Promise<void> {
    return this.session.calibrate();
  }

  /** A 1–20 key: scored with the active multiplier, which then falls back to
   * single — the multiplier applies to one dart, not to the rest of the visit. */
  protected enterNumber(value: number): void {
    this.game.registerDart(value * this.multiplier());
    this.multiplier.set(1);
  }

  /** A bull/miss key: its face value, unaffected by the D/T multiplier. */
  protected enterFixed(value: number): void {
    this.game.registerDart(value);
    this.multiplier.set(1);
  }

  protected toggleDouble(): void {
    this.multiplier.update((current) => (current === 2 ? 1 : 2));
  }

  protected toggleTriple(): void {
    this.multiplier.update((current) => (current === 3 ? 1 : 3));
  }

  ngOnDestroy(): void {
    // Leaving the game screen only pauses the loop; the session (camera + socket)
    // keeps running so returning is instant. Teardown is endGame() alone.
    this.session.detachView();
  }
}
