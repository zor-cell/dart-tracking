import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { Select } from 'primeng/select';
import { Slider } from 'primeng/slider';
import { ToggleSwitch } from 'primeng/toggleswitch';
import {
  AnnouncerService,
  AnnouncerTestResult,
  MAX_VOLUME,
} from '../../../announcement/services/announcer.service';
import { AnnouncerVoice, VOICE_NAMES } from '../../../announcement/models/announcer-voice';
import { AuthService } from '../../../auth/services/auth.service';
import { LANGUAGE_NAMES, Language } from '../../../../core/i18n/models/language';
import { LanguageService } from '../../../../core/i18n/services/language.service';
import { GameService } from '../../../game/services/game.service';
import { SettingsService } from '../../services/settings.service';
import { FavouriteDoublesComponent } from '../favourite-doubles/favourite-doubles.component';
import { LanguageSelectComponent } from '../language-select/language-select.component';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';

/** What the self-test's outcome is called on the page. */
const TEST_RESULTS: Record<AnnouncerTestResult, string> = {
  spoken: $localize`:@@settings.testResult.spoken:abgespielt`,
  failed: $localize`:@@settings.testResult.failed:abgebrochen`,
  no_answer: $localize`:@@settings.testResult.noAnswer:keine Rückmeldung`,
  muted: $localize`:@@settings.testResult.muted:stumm geschaltet`,
  unsupported: $localize`:@@settings.testResult.unsupported:nicht unterstützt`,
};

@Component({
  selector: 'app-settings',
  imports: [
    BackLinkComponent,
    Button,
    FavouriteDoublesComponent,
    FormsModule,
    LanguageSelectComponent,
    LoadingStateComponent,
    Select,
    Slider,
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
  private readonly appLanguage = inject(LanguageService).current;

  /** The debug and recording switches make the server write camera images, so
   * they are an admin's; the server masks them off for everyone else as well. */
  protected readonly isAdmin = this.auth.isAdmin;

  /** What is actually being recorded: the running game's flag, or the setting
   * the next one will adopt. */
  protected readonly evaluationEnabled = computed(
    () => this.game.state()?.evaluationEnabled ?? this.settings.evaluationEnabled(),
  );

  protected readonly maxVolume = MAX_VOLUME * 100;
  protected readonly volumePercent = computed(() => Math.round(this.announcer.volume() * 100));

  protected readonly announcerLanguageOptions: { label: string; value: Language | 'app' }[] = [
    { label: $localize`:@@settings.announcerLanguage.app:Wie die App`, value: 'app' },
    { label: LANGUAGE_NAMES.de, value: 'de' },
    { label: LANGUAGE_NAMES.en, value: 'en' },
  ];
  protected readonly announcerLanguage = computed(() => this.settings.announcerLanguage() ?? 'app');

  /** The voices by name in the language the announcer speaks. */
  protected readonly voiceOptions = computed(() => {
    const names = VOICE_NAMES[this.settings.announcerLanguage() ?? this.appLanguage];
    return (['first', 'second'] as const).map((voice) => ({ label: names[voice], value: voice }));
  });

  protected readonly testing = signal(false);
  protected readonly testResult = signal<string | null>(null);

  /** Play the server's test phrase and report what became of it; called straight
   * from the click, so the audio may start. */
  protected async testAnnouncement(): Promise<void> {
    const spoken = this.announcer.test();
    this.testing.set(true);
    this.testResult.set(TEST_RESULTS[await spoken]);
    this.testing.set(false);
  }

  protected setAnnouncerLanguage(language: Language | 'app'): void {
    this.settings.setAnnouncerLanguage(language === 'app' ? null : language);
  }

  protected setAnnouncerVoice(voice: AnnouncerVoice): void {
    this.settings.setAnnouncerVoice(voice);
  }

  protected setVolume(percent: number): void {
    this.announcer.setVolume(percent / 100);
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
