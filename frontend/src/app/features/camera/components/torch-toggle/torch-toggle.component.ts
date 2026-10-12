import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { Button } from 'primeng/button';
import { CameraService } from '../../services/camera.service';

/** Light button: switches the camera light, on devices that have one and let
 * the browser at it. */
@Component({
  selector: 'app-torch-toggle',
  imports: [Button],
  templateUrl: './torch-toggle.component.html',
  styleUrl: './torch-toggle.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TorchToggleComponent {
  protected readonly camera = inject(CameraService);

  protected onClick(): void {
    void this.camera.toggleTorch();
  }
}
