import { ChangeDetectionStrategy, Component, inject, model, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { Checkbox } from 'primeng/checkbox';
import { Dialog } from 'primeng/dialog';
import { Message } from 'primeng/message';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { DIALOG_STYLE } from '../../../../core/view/models/dialog-style';
import { AuthService } from '../../../auth/services/auth.service';
import { ExportService } from '../../services/export.service';

/** Confirms and downloads the account's data export; admins may add the camera frames. */
@Component({
  selector: 'app-export-dialog',
  imports: [ReactiveFormsModule, Button, Checkbox, Dialog, Message],
  templateUrl: './export-dialog.component.html',
  styleUrl: './export-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ExportDialogComponent {
  protected readonly dialogStyle = DIALOG_STYLE;
  private readonly exports = inject(ExportService);
  protected readonly isAdmin = inject(AuthService).isAdmin;

  readonly visible = model(false);

  protected readonly frames = new FormControl(false, { nonNullable: true });
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected async submit(): Promise<void> {
    if (this.busy()) {
      return;
    }
    this.busy.set(true);
    this.frames.disable();
    this.error.set(null);
    try {
      await this.exports.download(this.isAdmin() && this.frames.value);
      this.visible.set(false);
    } catch (failure) {
      this.error.set(
        httpErrorMessage(
          failure,
          {},
          $localize`:@@export.failed:Export fehlgeschlagen. Bitte erneut versuchen.`,
        ),
      );
    } finally {
      this.busy.set(false);
      this.frames.enable();
    }
  }

  protected reset(): void {
    this.frames.reset();
    this.error.set(null);
  }
}
