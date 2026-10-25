import { ChangeDetectionStrategy, Component, inject, model, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { AutoFocus } from 'primeng/autofocus';
import { Button } from 'primeng/button';
import { Dialog } from 'primeng/dialog';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { DISPLAY_NAME_MAX_LENGTH } from '../../../auth/models/profile-rules';
import { PlayerIdentityDto } from '../../dto/player-identity.dto';
import { playerNameError } from '../../models/player-name-error';
import { PlayerService } from '../../services/player.service';
import { FieldErrorComponent } from '../../../../core/view/components/field-error/field-error.component';
import { DIALOG_STYLE } from '../../../../core/view/models/dialog-style';

@Component({
  selector: 'app-player-create-dialog',
  imports: [AutoFocus, Button, Dialog, FieldErrorComponent, InputText, Message, ReactiveFormsModule],
  templateUrl: './player-create-dialog.component.html',
  styleUrl: './player-create-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlayerCreateDialogComponent {
  protected readonly dialogStyle = DIALOG_STYLE;
  private readonly players = inject(PlayerService);
  private readonly fb = inject(FormBuilder);

  readonly visible = model(false);
  readonly created = output<PlayerIdentityDto>();

  protected readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(DISPLAY_NAME_MAX_LENGTH)]],
  });
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  constructor() {
    this.form.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => this.error.set(null));
  }

  protected async submit(): Promise<void> {
    const name = this.form.controls.name.value.trim();
    if (!name || this.form.invalid || this.busy()) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    try {
      this.created.emit(await this.players.create(name));
      this.visible.set(false);
    } catch (failure) {
      this.error.set(playerNameError(failure));
    } finally {
      this.busy.set(false);
    }
  }

  protected reset(): void {
    this.form.reset();
    this.error.set(null);
  }
}
