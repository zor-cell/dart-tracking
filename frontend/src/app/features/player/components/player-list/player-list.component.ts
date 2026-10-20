import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ConfirmationService } from 'primeng/api';
import { AutoFocus } from 'primeng/autofocus';
import { Button } from 'primeng/button';
import { ConfirmDialog } from 'primeng/confirmdialog';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Tag } from 'primeng/tag';
import { Tooltip } from 'primeng/tooltip';
import { DISPLAY_NAME_MAX_LENGTH } from '../../../auth/models/profile-rules';
import { AuthService } from '../../../auth/services/auth.service';
import { PlayerIdentityDto } from '../../dto/player-identity.dto';
import { PlayerService } from '../../services/player.service';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';

const nameValidators = [Validators.required, Validators.maxLength(DISPLAY_NAME_MAX_LENGTH)];

@Component({
  selector: 'app-player-list',
  imports: [
    AutoFocus,
    BackLinkComponent,
    Button,
    ConfirmDialog,
    InputText,
    LoadingStateComponent,
    Message,
    NgTemplateOutlet,
    EmptyStateComponent,
    ReactiveFormsModule,
    Tag,
    Tooltip,
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

  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  private readonly entries = signal<PlayerIdentityDto[]>([]);

  protected readonly self = computed(() => this.entries().find((entry) => entry.isSelf));
  protected readonly others = computed(() => this.entries().filter((entry) => !entry.isSelf));

  protected readonly creating = signal(false);
  protected readonly createError = signal<string | null>(null);
  protected readonly createForm = this.fb.nonNullable.group({ name: ['', nameValidators] });

  protected readonly editingId = signal<string | null>(null);
  protected readonly busyId = signal<string | null>(null);
  protected readonly editError = signal<string | null>(null);
  protected readonly editForm = this.fb.nonNullable.group({ name: ['', nameValidators] });

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
      this.entries.set(await this.players.list());
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
      message: `${player.name} aus deiner Spielerliste entfernen? Bisherige Spiele behalten den Namen.`,
      icon: 'pi pi-exclamation-triangle',
      rejectButtonProps: { label: 'Abbrechen', severity: 'secondary', text: true },
      acceptButtonProps: { label: 'Entfernen', severity: 'danger' },
      accept: () => void this.remove(player),
    });
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
