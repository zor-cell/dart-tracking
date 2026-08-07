import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Accordion, AccordionContent, AccordionHeader, AccordionPanel } from 'primeng/accordion';
import { ToggleSwitch } from 'primeng/toggleswitch';
import { SettingsService } from '../../services/settings.service';

@Component({
  selector: 'app-settings',
  imports: [FormsModule, ToggleSwitch, Accordion, AccordionPanel, AccordionHeader, AccordionContent],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsComponent {
  protected readonly settings = inject(SettingsService);

  /** Values of the accordion panels that start expanded. */
  protected readonly openSections = signal<string[]>(['game']);
}
