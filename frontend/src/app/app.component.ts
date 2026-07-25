import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { BottomNavComponent } from './core/navigation/components/bottom-nav/bottom-nav.component';
import { GameTopBarComponent } from './features/game/components/game-top-bar/game-top-bar.component';
import { GameService } from './features/game/services/game.service';
import {Toast} from "primeng/toast";

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, BottomNavComponent, GameTopBarComponent, Toast],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  // Drives the game top-bar: it shows only while a game is active.
  protected readonly game = inject(GameService);

  protected readonly toastBreakpoints = {
    '640px': { width: '100%', right: '0', left: '0', transform: 'none' },
  };
}
