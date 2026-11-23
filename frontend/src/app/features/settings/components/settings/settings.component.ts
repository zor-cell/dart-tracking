import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  linkedSignal,
  signal,
} from '@angular/core';
import { NgOptimizedImage, NgTemplateOutlet } from '@angular/common';
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
import { LANGUAGE_FLAGS, LANGUAGE_NAMES, Language } from '../../../../core/i18n/models/language';
import { LanguageService } from '../../../../core/i18n/services/language.service';
import { GameService } from '../../../game/services/game.service';
import { SettingsService } from '../../services/settings.service';
import { FavouriteDoublesComponent } from '../favourite-doubles/favourite-doubles.component';
import { LanguageSelectComponent } from '../language-select/language-select.component';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { ConfirmService } from '../../../../core/view/services/confirm.service';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { ThemeMode } from '../../../../core/theme/models/theme';
import { ThemeService } from '../../../../core/theme/services/theme.service';

/** What the self-test's outcome is called on the page. */
const TEST_RESULTS: Record<AnnouncerTestResult, string> = {
  spoken: $localize`:@@settings.testResult.spoken:abgespielt`,
  failed: $localize`:@@settings.testResult.failed:abgebrochen`,
  no_answer: $localize`:@@settings.testResult.noAnswer:keine Rückmeldung`,
  muted: $localize`:@@settings.testResult.muted:stumm geschaltet`,
  unsupported: $localize`:@@settings.testResult.unsupported:nicht unterstützt`,
};

/** A dropdown option, shown with a flag or else an icon. */
interface SettingChoice<T> {
  readonly label: string;
  readonly value: T;
  readonly icon?: string;
  readonly flag?: string;
}

@Component({
  selector: 'app-settings',
  imports: [
    BackLinkComponent,
    Button,
    FavouriteDoublesComponent,
    FormsModule,
    InfoHintComponent,
    LanguageSelectComponent,
    NgOptimizedImage,
    NgTemplateOutlet,
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
  protected readonly theme = inject(ThemeService);

  protected readonly themeOptions: SettingChoice<ThemeMode>[] = [
    { label: $localize`:@@settings.theme.system:System`, value: 'system', icon: 'pi pi-desktop' },
    { label: $localize`:@@settings.theme.light:Hell`, value: 'light', icon: 'pi pi-sun' },
    { label: $localize`:@@settings.theme.dark:Dunkel`, value: 'dark', icon: 'pi pi-moon' },
  ];

  private readonly game = inject(GameService);
  private readonly auth = inject(AuthService);
  private readonly appLanguage = inject(LanguageService).current;

  /** Admins see the announcer's diagnostics. */
  protected readonly isAdmin = this.auth.isAdmin;
  private readonly confirm = inject(ConfirmService);

  /** The frame switch as shown: the setting, off already while switching off is asked. */
  protected readonly framesKept = linkedSignal(() => this.settings.evaluationEnabled());

  protected readonly maxVolume = MAX_VOLUME * 100;
  protected readonly volumePercent = computed(() => Math.round(this.announcer.volume() * 100));

  protected readonly announcerLanguageOptions: SettingChoice<Language | 'app'>[] = [
    { label: $localize`:@@settings.announcerLanguage.app:App`, value: 'app', icon: 'pi pi-mobile' },
    { label: LANGUAGE_NAMES.de, value: 'de', flag: LANGUAGE_FLAGS.de },
    { label: LANGUAGE_NAMES.en, value: 'en', flag: LANGUAGE_FLAGS.en },
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
   * Keep frames from now on, or stop after asking, since that deletes the kept ones.
   * Applied to the running game too, which the server takes from its owner only.
   */
  protected setFramesKept(kept: boolean): void {
    this.framesKept.set(kept);
    if (kept) {
      this.applyFramesKept(true);
      return;
    }
    this.confirm.ask(
      $localize`:@@settings.framesOff.title:Kamerabilder nicht mehr speichern?`,
      $localize`:@@settings.framesOff.message:Die bisher gespeicherten Kamerabilder deiner Spiele werden gelöscht.`,
      $localize`:@@settings.framesOff.action:Ausschalten`,
      () => this.applyFramesKept(false),
      false,
      () => this.framesKept.set(this.settings.evaluationEnabled()),
    );
  }

  /** Wired here rather than in the settings service, which the game service
   * depends on and so cannot depend on in turn. */
  private applyFramesKept(kept: boolean): void {
    this.settings.setEvaluationEnabled(kept);
    if (this.game.state()) {
      this.game.setEvaluation(kept);
    }
  }
}
