import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Button } from 'primeng/button';
import { CalibrationService } from '../../../calibration/services/calibration.service';
import { GameService } from '../../services/game.service';

/** Pause button: holds the camera's bookings on every device, while a camera is in the game. */
@Component({
  selector: 'app-tracking-toggle',
  imports: [Button],
  templateUrl: './tracking-toggle.component.html',
  styleUrl: './tracking-toggle.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrackingToggleComponent {
  private readonly game = inject(GameService);
  private readonly calibration = inject(CalibrationService);

  protected readonly paused = this.game.trackingPaused;
  protected readonly resumeLabel = $localize`:@@game.resumeTracking:Tracking fortsetzen`;
  protected readonly pauseLabel = $localize`:@@game.pauseTracking:Tracking pausieren`;
  protected readonly shown = computed(() => {
    const room = this.calibration.roomState();
    return room !== null && room !== 'no_camera' && this.game.settledWinner() === null;
  });

  protected onClick(): void {
    this.game.setTrackingPaused(!this.paused());
  }
}
