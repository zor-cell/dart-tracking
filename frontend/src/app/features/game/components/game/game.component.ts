import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  ElementRef,
  inject,
  OnDestroy,
  signal,
  viewChild,
} from '@angular/core';
import {RouterLink} from '@angular/router';
import {Button} from 'primeng/button';
import {BoardOverlayComponent} from '../../../calibration/components/board-overlay/board-overlay.component';
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
  imports: [RouterLink, Button, BoardOverlayComponent],
  templateUrl: './game.component.html',
  styleUrl: './game.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameComponent implements AfterViewInit, OnDestroy {
  protected readonly game = inject(GameService);
  protected readonly settings = inject(SettingsService);

  private readonly session = inject(GameSessionService);
  private readonly calibration = inject(CalibrationService);
  private readonly throwCapture = inject(FrameDiffService);
  private readonly detection = inject(DetectionService);

  private readonly videoRef = viewChild.required<ElementRef<HTMLVideoElement>>('video');
  private readonly diffCanvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('diffCanvas');
  private readonly captureCanvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('captureCanvas');
  private readonly detectionDebugCanvasRef =
    viewChild<ElementRef<HTMLCanvasElement>>('detectionDebugCanvas');

  protected readonly cameraPhase = this.session.phase;
  protected readonly cameraError = this.session.cameraError;
  protected readonly calibrationStatus = this.calibration.status;
  protected readonly calibrationOverlay = this.calibration.overlay;
  protected readonly detectionOverlay = this.detection.overlay;
  protected readonly detectionStatusLabel = this.throwCapture.statusLabel;
  protected readonly detectionFeedback = this.detection.feedbackLabel;
  protected readonly detectionDebug = this.throwCapture.debug;

  // The frame-diff debug overlay is on only while tracking and switched on.
  protected readonly debugActive = computed(
    () => this.settings.debugDetection() && this.cameraPhase() === 'tracking',
  );

  protected readonly padRows = PAD_ROWS;

  protected readonly multiplier = signal<1 | 2 | 3>(1);
  protected readonly multiplierPrefix = computed(() =>
    this.multiplier() === 2 ? 'D' : this.multiplier() === 3 ? 'T' : '',
  );

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
      this.throwCapture.setDebugCanvas(this.settings.debugDetection() ? canvas : null);
    });
  }

  ngAfterViewInit(): void {
    // Hand the session this view's elements: it either resumes an ongoing session
    // onto them (navigation) or, after a refresh, restores and resumes the game.
    this.session.attachView(
      this.videoRef().nativeElement,
      this.diffCanvasRef().nativeElement,
      this.captureCanvasRef().nativeElement,
    );
  }

  protected startCamera(): Promise<void> {
    return this.session.startCamera();
  }

  protected calibrateBoard(): Promise<void> {
    return this.session.calibrate();
  }

  /** End the game entirely: tear down the live session and clear the state. */
  protected endGame(): void {
    this.session.endSession();
    this.game.reset();
  }

  /** A 1–20 key: scored with the active multiplier, which stays set afterwards. */
  protected enterNumber(value: number): void {
    this.game.registerDart(value * this.multiplier());
  }

  /** A bull/miss key: its face value, unaffected by the D/T multiplier. */
  protected enterFixed(value: number): void {
    this.game.registerDart(value);
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
