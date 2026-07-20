import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { SettingsService } from '../../../settings/services/settings.service';
import { GameService } from '../../services/game.service';

const MAX_SINGLE_DART = 60;

@Component({
  selector: 'app-game',
  imports: [RouterLink, ReactiveFormsModule, Button, InputText],
  templateUrl: './game.component.html',
  styleUrl: './game.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameComponent {
  protected readonly game = inject(GameService);
  protected readonly settings = inject(SettingsService);

  // Fallback dart entry until the vision backend feeds scores reliably; can be
  // hidden via settings once camera detection is trusted (the undo button stays
  // available either way, since it also corrects camera mis-detections).
  protected readonly scoreControl = new FormControl<number | null>(null);

  // Placeholder slots so the turn always shows three dart positions.
  protected readonly emptySlots = computed(() =>
    Array.from({ length: this.game.state()?.dartsRemaining ?? 0 }),
  );

  constructor() {
    // After a page refresh the singleton state is empty; restore it from the server.
    this.game.restore();
  }

  protected submitScore(): void {
    const score = this.scoreControl.value;
    if (score !== null && score >= 0 && score <= MAX_SINGLE_DART) {
      this.game.registerDart(score);
      this.scoreControl.reset();
    }
  }
}
