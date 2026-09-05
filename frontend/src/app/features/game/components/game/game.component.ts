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
import {ProgressSpinner} from 'primeng/progressspinner';
import {OverlayComponent} from '../../../calibration/components/overlay/overlay.component';
import {CalibrationService} from '../../../calibration/services/calibration.service';
import {DetectionService} from '../../../detection/services/detection.service';
import {FrameDiffService} from '../../../detection/services/frame-diff.service';
import {SettingsService} from '../../../settings/services/settings.service';
import {DartDto} from '../../dto/dart.dto';
import {DARTS_PER_TURN} from '../../models/visit';
import {GameService} from '../../services/game.service';
import {GameSessionService} from '../../services/game-session.service';
import {GameTopBarComponent} from '../game-top-bar/game-top-bar.component';
import {VirtualBoardComponent} from '../virtual-board/virtual-board.component';

/** A side-column key: a fixed field, so it carries its own multiplier and is
 * unaffected by the D/T keys. */
type FixedKey = { readonly label: string; readonly value: number; readonly multiplier: number };

const MISS: FixedKey = { label: '0', value: 0, multiplier: 0 };
const OUTER_BULL: FixedKey = { label: '25', value: 25, multiplier: 1 };
const BULLSEYE: FixedKey = { label: '50', value: 25, multiplier: 2 };

/** Score keypad layout: four numbers per row, with the bull/miss keys down the
 * side column (top two rows have no side key). */
type PadRow = { readonly numbers: number[]; readonly side: FixedKey | null };

const PAD_ROWS: readonly PadRow[] = [
  { numbers: [1, 2, 3, 4], side: null },
  { numbers: [5, 6, 7, 8], side: null },
  { numbers: [9, 10, 11, 12], side: MISS },
  { numbers: [13, 14, 15, 16], side: OUTER_BULL },
  { numbers: [17, 18, 19, 20], side: BULLSEYE },
];

@Component({
  selector: 'app-game',
  imports: [
    RouterLink,
    Button,
    ProgressSpinner,
    OverlayComponent,
    VirtualBoardComponent,
    GameTopBarComponent,
  ],
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
  private readonly scoreboardRef = viewChild<ElementRef<HTMLUListElement>>('scoreboard');

  protected readonly deviceRole = this.session.role;
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

  /** The visit being thrown, drawn on the virtual board as it fills up. */
  protected readonly currentDarts = computed<readonly DartDto[]>(
    () => this.game.currentTurn()?.darts ?? [],
  );

  /**
   * How many player cards share the row's width. Up to three, so the thrower
   * keeps a neighbour on each side; beyond that the row scrolls.
   */
  protected readonly visiblePlayers = computed(() =>
    Math.min(this.game.state()?.players.length ?? 1, 3),
  );

  /**
   * The slots after the darts already thrown, carrying the checkout route where
   * there is one. Sized off the darts thrown rather than `dartsRemaining`: a
   * busted visit has none remaining, which would drop the boxes from the row.
   */
  protected readonly checkoutSlots = computed<(string | null)[]>(() => {
    const thrown = this.game.currentTurn()?.darts.length ?? 0;
    const checkout = this.game.state()?.checkout ?? null;
    return Array.from({ length: DARTS_PER_TURN - thrown }, (_, index) => checkout?.[index] ?? null);
  });

  constructor() {
    // Follow play along the row, so the thrower stays in the middle and the two
    // around them stay in view. A no-op while everyone fits.
    effect(() => {
      const index = this.game.state()?.currentPlayerIndex;
      const list = this.scoreboardRef()?.nativeElement;
      if (list === undefined || index === undefined) {
        return;
      }
      const card = list.children.item(index) as HTMLElement | null;
      if (card !== null) {
        list.scrollTo({ left: card.offsetLeft + card.offsetWidth / 2 - list.clientWidth / 2 });
      }
    });

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

  /** Scoreboard counterpart to `calibrateBoard`: this device has no picture, so
   * it asks the game's cameras to take one. */
  protected requestCalibration(): void {
    this.calibration.requestCalibration();
  }

  /** A 1–20 key: booked with the active multiplier, which then falls back to
   * single — the multiplier applies to one dart, not to the rest of the visit. */
  protected enterNumber(value: number): void {
    this.game.registerDart(value, this.multiplier());
    this.multiplier.set(1);
  }

  /** A bull/miss key: its own fixed field, unaffected by the D/T multiplier. */
  protected enterFixed(key: FixedKey): void {
    this.game.registerDart(key.value, key.multiplier);
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
