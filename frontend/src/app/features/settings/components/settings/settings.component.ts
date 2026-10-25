import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { ToggleSwitch } from 'primeng/toggleswitch';
import {
  AnnouncerService,
  AnnouncerTestResult,
} from '../../../announcement/services/announcer.service';
import { AuthService } from '../../../auth/services/auth.service';
import { GameService } from '../../../game/services/game.service';
import { SettingsService } from '../../services/settings.service';
import { FavouriteDoublesComponent } from '../favourite-doubles/favourite-doubles.component';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';

/** What the self-test's outcome is called on the page. */
const TEST_RESULTS: Record<AnnouncerTestResult, string> = {
  spoken: 'gesprochen',
  failed: 'abgebrochen',
  no_answer: 'keine Rückmeldung',
  muted: 'stumm geschaltet',
  unsupported: 'nicht unterstützt',
};

@Component({
  selector: 'app-settings',
  imports: [
    BackLinkComponent,
    Button,
    FavouriteDoublesComponent,
    FormsModule,
    LoadingStateComponent,
    ToggleSwitch,
  ],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsComponent {
  protected readonly settings = inject(SettingsService);

  protected readonly announcer = inject(AnnouncerService);

  private readonly game = inject(GameService);
  private readonly auth = inject(AuthService);

  /** The debug and recording switches make the server write camera images, so
   * they are an admin's; the server masks them off for everyone else as well. */
  protected readonly isAdmin = this.auth.isAdmin;

  /** What is actually being recorded: the running game's flag, or the setting
   * the next one will adopt. */
  protected readonly evaluationEnabled = computed(
    () => this.game.state()?.evaluationEnabled ?? this.settings.evaluationEnabled(),
  );

  protected readonly testing = signal(false);
  protected readonly testResult = signal<string | null>(null);

  /**
   * Say a phrase out loud and report what the synthesiser did with it. Nothing
   * may be awaited before the utterance goes out, or WebKit drops it.
   */
  protected async testAnnouncement(): Promise<void> {
    const spoken = this.announcer.test();
    this.testing.set(true);
    this.testResult.set(TEST_RESULTS[await spoken]);
    this.testing.set(false);
  }

  /**
   * Remember the choice for the games this device opens, and apply it to the one
   * already running. Wired here rather than in the settings service, which the
   * game service depends on and so cannot depend on in turn.
   */
  protected setEvaluationEnabled(enabled: boolean): void {
    this.settings.setEvaluationEnabled(enabled);
    if (this.game.state()) {
      this.game.setEvaluation(enabled);
    }
  }
}
