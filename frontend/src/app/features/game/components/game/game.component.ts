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
import {FormControl, ReactiveFormsModule} from '@angular/forms';
import {RouterLink} from '@angular/router';
import {Button} from 'primeng/button';
import {InputText} from 'primeng/inputtext';
import {BoardOverlayComponent} from '../../../tracking/components/board-overlay/board-overlay.component';
import {CalibrationService} from '../../../tracking/services/calibration.service';
import {CameraService} from '../../../tracking/services/camera.service';
import {SocketService} from '../../../tracking/services/socket.service';
import {FrameDiffService} from '../../../tracking/services/frame-diff.service';
import {SettingsService} from '../../../settings/services/settings.service';
import {CameraPhase} from '../../models/camera-phase';
import {GameService} from '../../services/game.service';

const MAX_SINGLE_DART = 60;

@Component({
  selector: 'app-game',
  imports: [RouterLink, ReactiveFormsModule, Button, InputText, BoardOverlayComponent],
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

  private readonly videoRef = viewChild.required<ElementRef<HTMLVideoElement>>('video');
  private readonly diffCanvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('diffCanvas');
  private readonly captureCanvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('captureCanvas');

  protected readonly cameraPhase = signal<CameraPhase>('idle');
  protected readonly cameraError = this.camera.error;
  protected readonly calibrationStatus = this.calibration.status;
  protected readonly calibrationOverlay = this.calibration.overlay;
  protected readonly detectionStatusLabel = this.throwCapture.statusLabel;

  protected readonly scoreControl = new FormControl<number | null>(null);

  protected readonly emptySlots = computed(() =>
    Array.from({ length: this.game.state()?.dartsRemaining ?? 0 }),
  );

  constructor() {
    this.game.restore();

    effect(() => {
      if (this.calibrationStatus() === 'success' && this.cameraPhase() === 'calibrating') {
        this.startTracking();
      }
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

  protected submitScore(): void {
    const score = this.scoreControl.value;
    if (score !== null && score >= 0 && score <= MAX_SINGLE_DART) {
      this.game.registerDart(score);
      this.scoreControl.reset();
    }
  }

  ngOnDestroy(): void {
    this.throwCapture.stopDetectionLoop();
    this.camera.stop();
    this.socket.disconnect();
  }
}
