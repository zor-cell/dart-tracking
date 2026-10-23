import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { Checkbox } from 'primeng/checkbox';
import { Message } from 'primeng/message';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { InvitationDto } from '../../dto/invitation.dto';
import { PlayerService } from '../../services/player.service';

type InvitationState = 'loading' | 'ready' | 'accepted' | 'failed';

/** Landing point of an invitation link (`/invite/:token`): shows what would be
 * linked and links it once the signed-in account agrees. */
@Component({
  selector: 'app-player-invitation',
  imports: [
    Button,
    Checkbox,
    EmptyStateComponent,
    LoadingStateComponent,
    Message,
    ReactiveFormsModule,
    RouterLink,
  ],
  templateUrl: './player-invitation.component.html',
  styleUrl: './player-invitation.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlayerInvitationComponent {
  private readonly players = inject(PlayerService);
  private readonly token = inject(ActivatedRoute).snapshot.paramMap.get('token') ?? '';

  protected readonly state = signal<InvitationState>('loading');
  protected readonly invitation = signal<InvitationDto | null>(null);
  protected readonly error = signal('');
  protected readonly acceptError = signal<string | null>(null);
  protected readonly accepting = signal(false);
  protected readonly reciprocal = new FormControl(true, { nonNullable: true });

  protected readonly historyText = computed(() => {
    const count = this.invitation()?.gameCount ?? 0;
    if (count === 0) {
      return 'Eure künftigen Spiele erscheinen dann in deinem Verlauf und deiner Statistik.';
    }
    const past = count === 1 ? 'Das bisherige Spiel' : `Die ${count} bisherigen Spiele`;
    return `${past} und alle künftigen erscheinen dann in deinem Verlauf und deiner Statistik.`;
  });

  protected readonly reciprocalLabel = computed(() => {
    const invitation = this.invitation();
    if (invitation === null) {
      return '';
    }
    return invitation.reciprocal === 'link'
      ? `Deinen Spieler „${invitation.inviterName}“ ebenfalls mit diesem Konto verknüpfen`
      : `${invitation.inviterName} auch zu deinen Spielern hinzufügen`;
  });

  protected readonly acceptedText = computed(
    () =>
      `Verknüpft. Die Spiele von ${this.invitation()?.inviterName ?? ''} mit dir erscheinen jetzt in deinem Verlauf.`,
  );

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    try {
      this.invitation.set(await this.players.previewInvitation(this.token));
      this.state.set('ready');
    } catch (failure) {
      this.error.set(describe(failure, 'Die Einladung konnte nicht geladen werden.'));
      this.state.set('failed');
    }
  }

  protected async accept(): Promise<void> {
    const invitation = this.invitation();
    if (invitation === null || this.accepting()) {
      return;
    }
    this.accepting.set(true);
    this.acceptError.set(null);
    try {
      await this.players.acceptInvitation(
        this.token,
        invitation.reciprocal !== 'none' && this.reciprocal.value,
      );
      this.state.set('accepted');
    } catch (failure) {
      this.acceptError.set(
        describe(failure, 'Die Verknüpfung ist fehlgeschlagen. Bitte später erneut versuchen.'),
      );
    } finally {
      this.accepting.set(false);
    }
  }
}

function describe(failure: unknown, fallback: string): string {
  return httpErrorMessage(
    failure,
    {
      400: 'Das ist dein eigener Link. Öffne ihn auf dem Gerät der Person, die du verknüpfen möchtest.',
      404: 'Der Link ist ungültig, abgelaufen oder wurde schon verwendet.',
      409: 'Du bist in dieser Spielerliste schon mit einem anderen Spieler verknüpft.',
    },
    fallback,
  );
}
