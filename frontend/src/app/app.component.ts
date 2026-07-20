import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { BottomNavComponent } from './core/navigation/components/bottom-nav/bottom-nav.component';
import {Toast} from "primeng/toast";

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, BottomNavComponent, Toast],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  protected readonly toastBreakpoints = {
    '640px': { width: '100%', right: '0', left: '0', transform: 'none' },
  };
}
