import { DOCUMENT, DatePipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ConfirmationService } from 'primeng/api';
import { AutoFocus } from 'primeng/autofocus';
import { Button } from 'primeng/button';
import { ConfirmDialog } from 'primeng/confirmdialog';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { Tag } from 'primeng/tag';
import { DISPLAY_NAME_MAX_LENGTH } from '../../../auth/models/profile-rules';
import { AuthService } from '../../../auth/services/auth.service';
import { PlayerIdentityDto } from '../../dto/player-identity.dto';
import { LINK_STATE_LABELS, LinkState } from '../../models/player-filter';
import { PlayerService } from '../../services/player.service';
import { PlayerLinksComponent } from '../player-links/player-links.component';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { FieldErrorComponent } from '../../../../core/view/components/field-error/field-error.component';
import { ShareDialogComponent } from '../../../../core/view/components/share-dialog/share-dialog.component';
import { ListToolbarComponent } from '../../../../core/view/components/list-toolbar/list-toolbar.component';
import { FilterChip } from '../../../../core/view/models/filter-chip';
import { PagedTable } from '../../../../core/view/models/paged-table';

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
    ListToolbarComponent,
    LoadErrorComponent,
    FieldErrorComponent,
    PlayerLinksComponent,
    ReactiveFormsModule,
    Select,
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

  protected readonly query = signal('');
  protected readonly filters = this.fb.group({ linked: this.fb.control<LinkState | null>(null) });
  protected readonly linkOptions = Object.entries(LINK_STATE_LABELS).map(([value, label]) => ({
    label,
    value: value as LinkState,
  }));
  private readonly filterValue = toSignal(this.filters.valueChanges, {
    initialValue: this.filters.value,
  });
  protected readonly chips = computed<FilterChip[]>(() => {
    const linked = this.filterValue().linked;
    return linked ? [{ key: 'linked', label: LINK_STATE_LABELS[linked] }] : [];
  });
  /** Whether the search or a filter narrows the list. */
  protected readonly filtered = computed(() => this.query() !== '' || this.chips().length > 0);

  protected readonly entries = new PagedTable<PlayerIdentityDto>((limit, offset) =>
    this.players.page(limit, offset, {
      query: this.query() || null,
      linked: this.filters.getRawValue().linked,
    }),
  );
  private readonly self = computed(() => this.entries.items().find((entry) => entry.isSelf));

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
    void this.entries.load();
    this.createForm.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.createError.set(null));
    this.editForm.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => this.editError.set(null));
    this.filters.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => this.entries.restart());
  }

  protected onSearch(query: string): void {
    this.query.set(query);
    this.entries.restart();
  }

  protected clearFilter(key: string): void {
    this.filters.get(key)?.reset();
  }

  protected async create(): Promise<void> {
    const name = this.createForm.controls.name.value.trim();
    if (!name || this.createForm.invalid || this.creating()) {
      return;
    }
    this.creating.set(true);
    this.createError.set(null);
    try {
      await this.players.create(name);
      this.createForm.reset();
      await this.entries.load();
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
      this.entries.items.update((list) =>
        list.map((entry) => (entry.id === id ? renamed : entry)),
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
      this.entries.items.update((list) =>
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
      await this.entries.load();
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

function describe(failure: unknown): string {
  return httpErrorMessage(
    failure,
    { 409: 'Diesen Namen gibt es schon in deiner Spielerliste.' },
    'Speichern fehlgeschlagen. Bitte später erneut versuchen.',
  );
}
