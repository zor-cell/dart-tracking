import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { NgOptimizedImage } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SelectButton } from 'primeng/selectbutton';
import { LANGUAGE_FLAGS, LANGUAGE_NAMES, Language } from '../../../../core/i18n/models/language';
import { LanguageService } from '../../../../core/i18n/services/language.service';
import { SettingsService } from '../../services/settings.service';

/** Picks the app's language; the page reloads in the new one. */
@Component({
  selector: 'app-language-select',
  imports: [FormsModule, NgOptimizedImage, SelectButton],
  templateUrl: './language-select.component.html',
  styleUrl: './language-select.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LanguageSelectComponent {
  private readonly settings = inject(SettingsService);

  readonly labelledBy = input<string>();
  readonly size = input<'small' | 'large'>();

  protected readonly options = (Object.keys(LANGUAGE_NAMES) as Language[]).map((value) => ({
    value,
    label: LANGUAGE_NAMES[value],
    flag: LANGUAGE_FLAGS[value],
  }));

  protected readonly language = signal(inject(LanguageService).current);

  protected select(language: Language): void {
    this.language.set(language);
    void this.settings.setLanguage(language);
  }
}
