import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input, model } from '@angular/core';
import { QRCodeComponent } from 'angularx-qrcode';
import { Button } from 'primeng/button';
import { Dialog } from 'primeng/dialog';
import { Divider } from 'primeng/divider';
import { InputText } from 'primeng/inputtext';
import { NotificationService } from '../../../notification/services/notification.service';

/** A link to hand to another phone: as QR code, as copyable text and through the
 * system share sheet where the browser offers one. */
@Component({
  selector: 'app-share-dialog',
  imports: [Button, Dialog, Divider, InputText, QRCodeComponent],
  templateUrl: './share-dialog.component.html',
  styleUrl: './share-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ShareDialogComponent {
  private readonly document = inject(DOCUMENT);
  private readonly notification = inject(NotificationService);

  readonly visible = model(false);
  readonly header = input.required<string>();
  readonly url = input.required<string>();
  readonly hint = input('');
  /** Message placed before the link in the share sheet. */
  readonly shareText = input('');
  readonly qrAlt = input('QR-Code mit dem Link');

  protected readonly canShare = typeof this.document.defaultView?.navigator.share === 'function';

  /** Select the whole link on focus, so copying by hand is one keystroke away. */
  protected selectLink(event: Event): void {
    (event.target as HTMLInputElement).select();
  }

  /** The Clipboard API needs a secure context, which plain HTTP on a LAN address
   * is not — so a failure there says what to do instead. */
  protected async copyLink(): Promise<void> {
    try {
      await this.document.defaultView?.navigator.clipboard.writeText(this.url());
      this.notification.showSuccess('Link kopiert.');
    } catch {
      this.notification.showWarning('Kopieren nicht möglich — bitte den QR-Code scannen.');
    }
  }

  protected async share(): Promise<void> {
    try {
      await this.document.defaultView?.navigator.share({
        title: this.header(),
        text: this.shareText() || undefined,
        url: this.url(),
      });
    } catch {
      // Closing the share sheet rejects as well; the dialog stays open either way.
    }
  }
}
