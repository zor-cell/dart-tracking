import { DOCUMENT, DatePipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ConfirmationService } from 'primeng/api';
import { AutoFocus } from 'primeng/autofocus';
import { Button } from 'primeng/button';
import { ConfirmDialog } from 'primeng/confirmdialog';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { TableModule } from 'primeng/table';
import { Tag } from 'primeng/tag';
import { DISPLAY_NAME_MAX_LENGTH } from '../../../auth/models/profile-rules';
import { AuthService } from '../../../auth/services/auth.service';
import { PlayerIdentityDto } from '../../dto/player-identity.dto';
import { PlayerService } from '../../services/player.service';
import { PlayerLinksComponent } from '../player-links/player-links.component';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { FieldErrorComponent } from '../../../../core/view/components/field-error/field-error.component';
import { ShareDialogComponent } from '../../../../core/view/components/share-dialog/share-dialog.component';
import { PAGE_SIZE } from '../../../../core/view/models/page-size';

const nameValidators = [Validators.required, Validators.maxLength(DISPLAY_NAME_MAX_LENGTH)];

/** An invitation link handed out for one player of the list. */
interface Invitation {
  readonly name: string;
  readonly url: string;
  readonly expiresAt: string;
}

@Component({
  selector: 'app-player-list',
  imports: [
    AutoFocus,
    BackLinkComponent,
    Button,
    ConfirmDialog,
    DatePipe,
    EmptyStateComponent,
    InputText,
    LoadingStateComponent,
    Message,
    NgTemplateOutlet,
    LoadErrorComponent,
    FieldErrorComponent,
    PlayerLinksComponent,
    ReactiveFormsModule,
    ShareDialogComponent,
    TableModule,
    Tag,
  ],
  templateUrl: './player-list.component.html',
  styleUrl: './player-list.component.scss',
  providers: [ConfirmationService],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlayerListComponent {
  private readonly players = inject(PlayerService);
  private readonly auth = inject(AuthService);
  private readonly confirmation = inject(ConfirmationService);
  private readonly fb = inject(FormBuilder);
  private readonly document = inject(DOCUMENT);

  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  protected readonly pageSize = PAGE_SIZE;
  protected readonly entries = signal<PlayerIdentityDto[]>([]);

  protected readonly self = computed(() => this.entries().find((entry) => entry.isSelf));
  protected readonly others = computed(() => this.entries().filter((entry) => !entry.isSelf));

  protected readonly creating = signal(false);
  protected readonly createError = signal<string | null>(null);
  protected readonly createForm = this.fb.nonNullable.group({ name: ['', nameValidators] });

  protected readonly editingId = signal<string | null>(null);
  protected readonly busyId = signal<string | null>(null);
  protected readonly editError = signal<string | null>(null);
  protected readonly editForm = this.fb.nonNullable.group({ name: ['', nameValidators] });

  protected readonly invitation = signal<Invitation | null>(null);
  protected readonly invitationOpen = signal(false);
  protected readonly invitationHint = computed(() => {
    const name = this.invitation()?.name ?? '';
    return `${name} scannt den QR-Code oder öffnet den Link und meldet sich an. Danach zählen eure Spiele auch in der Statistik von ${name}.`;
  });
  protected readonly invitationShareText = computed(
    () => `Verknüpfe dein Dart-Konto mit „${this.invitation()?.name ?? ''}“ in meiner Spielerliste:`,
  );

  constructor() {
    void this.load();
    this.createForm.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.createError.set(null));
    this.editForm.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => this.editError.set(null));
  }

  protected async load(): Promise<void> {
    this.loading.set(true);
    this.failed.set(false);
    try {
      this.entries.set(await this.players.list(true));
    } catch {
      this.failed.set(true);
    } finally {
      this.loading.set(false);
    }
  }

  protected async create(): Promise<void> {
    const name = this.createForm.controls.name.value.trim();
    if (!name || this.createForm.invalid || this.creating()) {
      return;
    }
    this.creating.set(true);
    this.createError.set(null);
    try {
      const created = await this.players.create(name);
      this.entries.update((list) => ordered([...list, created]));
      this.createForm.reset();
    } catch (failure) {
      this.createError.set(describe(failure));
    } finally {
      this.creating.set(false);
    }
  }

  protected edit(player: PlayerIdentityDto): void {
    this.editForm.setValue({ name: player.name });
    this.editError.set(null);
    this.editingId.set(player.id);
  }

  protected cancel(): void {
    this.editingId.set(null);
    this.editError.set(null);
  }

  protected async save(): Promise<void> {
    const id = this.editingId();
    const name = this.editForm.controls.name.value.trim();
    if (id === null || !name || this.editForm.invalid || this.busyId()) {
      return;
    }
    this.busyId.set(id);
    this.editError.set(null);
    try {
      const renamed =
        id === this.self()?.id ? await this.renameSelf(name) : await this.players.rename(id, name);
      this.entries.update((list) =>
        ordered(list.map((entry) => (entry.id === id ? renamed : entry))),
      );
      this.editingId.set(null);
    } catch (failure) {
      this.editError.set(describe(failure));
    } finally {
      this.busyId.set(null);
    }
  }

  protected confirmRemove(player: PlayerIdentityDto): void {
    this.confirmation.confirm({
      header: 'Spieler entfernen',
      message: player.linked
        ? `${player.name} aus deiner Spielerliste entfernen? Das verknüpfte Konto behält die bisherigen Spiele in seiner Statistik.`
        : `${player.name} aus deiner Spielerliste entfernen? Bisherige Spiele behalten den Namen.`,
      icon: 'pi pi-exclamation-triangle',
      rejectButtonProps: { label: 'Abbrechen', severity: 'secondary', text: true },
      acceptButtonProps: { label: 'Entfernen', severity: 'danger' },
      accept: () => void this.remove(player),
    });
  }

  protected async invite(player: PlayerIdentityDto): Promise<void> {
    this.busyId.set(player.id);
    try {
      const link = await this.players.invite(player.id);
      this.invitation.set({
        name: player.name,
        url: `${this.document.location.origin}/invite/${link.token}`,
        expiresAt: link.expiresAt,
      });
      this.invitationOpen.set(true);
    } catch {
      // The error banner already says what went wrong.
    } finally {
      this.busyId.set(null);
    }
  }

  protected confirmUnlink(player: PlayerIdentityDto): void {
    this.confirmation.confirm({
      header: 'Verknüpfung lösen',
      message: `${player.name} ist dann nicht mehr mit einem Konto verknüpft. Die bisherigen Spiele bleiben in dessen Statistik, neue zählen dort nicht mehr.`,
      icon: 'pi pi-exclamation-triangle',
      rejectButtonProps: { label: 'Abbrechen', severity: 'secondary', text: true },
      acceptButtonProps: { label: 'Lösen', severity: 'danger' },
      accept: () => void this.unlink(player),
    });
  }

  private async unlink(player: PlayerIdentityDto): Promise<void> {
    this.busyId.set(player.id);
    try {
      const unlinked = await this.players.unlink(player.id);
      this.entries.update((list) =>
        list.map((entry) => (entry.id === player.id ? unlinked : entry)),
      );
    } catch {
      // The error banner already says what went wrong.
    } finally {
      this.busyId.set(null);
    }
  }

  private async remove(player: PlayerIdentityDto): Promise<void> {
    this.busyId.set(player.id);
    try {
      await this.players.remove(player.id);
      this.entries.update((list) => list.filter((entry) => entry.id !== player.id));
    } catch {
      // The error banner already says what went wrong.
    } finally {
      this.busyId.set(null);
    }
  }

  /** The own entry carries the account's display name, so it is renamed there. */
  private async renameSelf(name: string): Promise<PlayerIdentityDto> {
    const account = this.auth.user();
    const self = this.self();
    if (!account || !self) {
      throw new Error('no session');
    }
    await this.auth.updateProfile({ username: account.username, displayName: name });
    return { ...self, name };
  }
}

/** Own entry first, then alphabetical, as the server lists them. */
function ordered(list: PlayerIdentityDto[]): PlayerIdentityDto[] {
  return list.sort((a, b) => Number(b.isSelf) - Number(a.isSelf) || a.name.localeCompare(b.name));
}

function describe(failure: unknown): string {
  return httpErrorMessage(
    failure,
    { 409: 'Diesen Namen gibt es schon in deiner Spielerliste.' },
    'Speichern fehlgeschlagen. Bitte später erneut versuchen.',
  );
}
