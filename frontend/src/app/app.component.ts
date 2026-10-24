import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { BottomNavComponent } from './core/navigation/components/bottom-nav/bottom-nav.component';
import {Toast} from "primeng/toast";
import { ConfirmDialog } from 'primeng/confirmdialog';
import { DIALOG_STYLE } from './core/view/models/dialog-style';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, BottomNavComponent, ConfirmDialog, Toast],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  /** Just above the bottom nav, which is 3.5rem tall plus the home-indicator inset. */
  protected readonly toastStyle = { bottom: 'calc(4.25rem + env(safe-area-inset-bottom))' };
  protected readonly dialogStyle = DIALOG_STYLE;
  protected readonly toastBreakpoints = {
    '640px': { width: '100%', right: '0', left: '0', transform: 'none' },
  };
}
