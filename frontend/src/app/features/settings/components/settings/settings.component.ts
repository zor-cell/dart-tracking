import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Accordion, AccordionContent, AccordionHeader, AccordionPanel } from 'primeng/accordion';
import { Button } from 'primeng/button';
import { ToggleSwitch } from 'primeng/toggleswitch';
import { GameService } from '../../../game/services/game.service';
import { SettingsService } from '../../services/settings.service';

@Component({
  selector: 'app-settings',
  imports: [
    FormsModule,
    RouterLink,
    Button,
    ToggleSwitch,
    Accordion,
    AccordionPanel,
    AccordionHeader,
    AccordionContent,
  ],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsComponent {
  protected readonly settings = inject(SettingsService);

  private readonly game = inject(GameService);

  /** Values of the accordion panels that start expanded. */
  protected readonly openSections = signal<string[]>(['game']);

  /** What is actually being recorded: the running game's flag, or the setting
   * the next one will adopt. */
  protected readonly evaluationEnabled = computed(
    () => this.game.state()?.evaluationEnabled ?? this.settings.evaluationEnabled(),
  );

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
