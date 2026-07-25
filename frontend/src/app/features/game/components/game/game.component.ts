import {
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
import {CameraService} from '../../../camera/services/camera.service';
import {SocketService} from '../../../../core/socket/services/socket.service';
import {DetectionService} from '../../../detection/services/detection.service';
import {FrameDiffService} from '../../../detection/services/frame-diff.service';
import {SettingsService} from '../../../settings/services/settings.service';
import {CameraPhase} from '../../models/camera-phase';
import {GameService} from '../../services/game.service';

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
export class GameComponent implements OnDestroy {
  protected readonly game = inject(GameService);
  protected readonly settings = inject(SettingsService);

  private readonly camera = inject(CameraService);
  private readonly socket = inject(SocketService);
  private readonly calibration = inject(CalibrationService);
  private readonly throwCapture = inject(FrameDiffService);
  private readonly detection = inject(DetectionService);

  private readonly videoRef = viewChild.required<ElementRef<HTMLVideoElement>>('video');
  private readonly diffCanvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('diffCanvas');
  private readonly captureCanvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('captureCanvas');
  // Only in the DOM while the debug overlay is shown, hence optional.
  private readonly detectionDebugCanvasRef =
    viewChild<ElementRef<HTMLCanvasElement>>('detectionDebugCanvas');

  protected readonly cameraPhase = signal<CameraPhase>('idle');
  protected readonly cameraError = this.camera.error;
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

  // Sticky multiplier for the keypad: pressing D/T marks every number key with a
  // D/T so a run of doubles or triples needs no extra taps; press it again (or
  // switch) to change it. Bull/miss keys ignore it.
  protected readonly multiplier = signal<1 | 2 | 3>(1);
  // Prefixed onto every number key while active, e.g. "D15" / "T15".
  protected readonly multiplierPrefix = computed(() =>
    this.multiplier() === 2 ? 'D' : this.multiplier() === 3 ? 'T' : '',
  );

  // One entry per dart still to throw this turn. A suggested checkout fills the
  // leading slots (its darts are thrown next); any slot beyond the checkout —
  // or every slot when there is no checkout — stays null and renders as "–".
  protected readonly checkoutSlots = computed<(string | null)[]>(() => {
    const state = this.game.state();
    const remaining = state?.dartsRemaining ?? 0;
    const checkout = state?.checkout ?? null;
    return Array.from({ length: remaining }, (_, index) => checkout?.[index] ?? null);
  });

  constructor() {
    this.game.restore();

    effect(() => {
      if (this.calibrationStatus() === 'success' && this.cameraPhase() === 'calibrating') {
        this.startTracking();
      }
    });

    // Attach the change-mask canvas whenever the debug panel is on screen, and
    // detach it the moment it leaves — keeping the loop's debug work off unless
    // someone is watching.
    effect(() => {
      const canvas = this.detectionDebugCanvasRef()?.nativeElement ?? null;
      this.throwCapture.setDebugCanvas(this.settings.debugDetection() ? canvas : null);
    });
  }

  protected async startCamera(gameId: string): Promise<void> {
    const video = this.videoRef().nativeElement;
    video.srcObject = await this.camera.start();
    await video.play();

    this.socket.connect(gameId);
    this.calibration.reset();
    this.cameraPhase.set('calibrating');
  }

  protected async calibrateBoard(): Promise<void> {
    await this.calibration.calibrate(this.videoRef().nativeElement, this.captureCanvasRef().nativeElement);
  }

  private startTracking(): void {
    this.throwCapture.startDetectionLoop(
      this.videoRef().nativeElement,
      this.diffCanvasRef().nativeElement,
      this.captureCanvasRef().nativeElement,
    );
    this.cameraPhase.set('tracking');
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
    this.throwCapture.stopDetectionLoop();
    this.camera.stop();
    this.socket.disconnect();
  }
}
