import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Button } from 'primeng/button';
import { AnnouncerService } from '../../services/announcer.service';

/** Speaker button: pulls the announcement onto this device, or mutes it here. */
@Component({
  selector: 'app-announcer-toggle',
  imports: [Button],
  templateUrl: './announcer-toggle.component.html',
  styleUrl: './announcer-toggle.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnnouncerToggleComponent {
  protected readonly announcer = inject(AnnouncerService);

  protected readonly icon = computed(() =>
    this.announcer.isAnnouncer() && !this.announcer.muted() ? 'pi pi-volume-up' : 'pi pi-volume-off',
  );

  protected readonly label = computed(() => {
    if (!this.announcer.isAnnouncer()) {
      return $localize`:@@announcer.claim:Ansage auf dieses Gerät holen`;
    }
    return this.announcer.muted()
      ? $localize`:@@announcer.unmute:Ansage einschalten`
      : $localize`:@@announcer.mute:Ansage stummschalten`;
  });

  protected onClick(): void {
    if (this.announcer.isAnnouncer()) {
      this.announcer.toggleMuted();
    } else {
      this.announcer.claim();
    }
  }
}
