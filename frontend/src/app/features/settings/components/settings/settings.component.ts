import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ToggleSwitch } from 'primeng/toggleswitch';
import { SettingsService } from '../../services/settings.service';

@Component({
  selector: 'app-settings',
  imports: [FormsModule, ToggleSwitch],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsComponent {
  protected readonly settings = inject(SettingsService);
}
