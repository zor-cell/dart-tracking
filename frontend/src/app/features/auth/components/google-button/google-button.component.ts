import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  LOCALE_ID,
  afterNextRender,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { Skeleton } from 'primeng/skeleton';
import { GoogleButtonText } from '../../models/google-identity';
import { GoogleIdentityService } from '../../services/google-identity.service';

/** Google's own sign-in button; emits the ID token of the account the user picked. */
@Component({
  selector: 'app-google-button',
  imports: [Skeleton],
  templateUrl: './google-button.component.html',
  styleUrl: './google-button.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GoogleButtonComponent {
  private readonly google = inject(GoogleIdentityService);
  private readonly locale = inject(LOCALE_ID);
  private readonly slot = viewChild.required<ElementRef<HTMLElement>>('slot');

  readonly text = input<GoogleButtonText>('signin_with');
  readonly credential = output<string>();

  protected readonly unavailable = signal(false);
  protected readonly settled = signal(false);
  private readonly receive = (credential: string): void => this.credential.emit(credential);

  constructor() {
    let sizing: ResizeObserver | null = null;
    afterNextRender(() => {
      // Google draws the button at a fixed pixel width, so wait until the slot has one.
      sizing = new ResizeObserver(([entry]) => {
        if (entry.contentRect.width > 0) {
          sizing?.disconnect();
          void this.render(entry.contentRect.width);
        }
      });
      sizing.observe(this.slot().nativeElement);
    });
    inject(DestroyRef).onDestroy(() => {
      sizing?.disconnect();
      this.google.release(this.receive);
    });
  }

  private async render(width: number): Promise<void> {
    const slot = this.slot().nativeElement;
    const view = slot.ownerDocument.defaultView;
    const dark = view?.matchMedia('(prefers-color-scheme: dark)').matches ?? false;
    try {
      await this.google.renderButton(
        slot,
        {
          type: 'standard',
          theme: dark ? 'filled_black' : 'outline',
          size: 'large',
          text: this.text(),
          shape: 'rectangular',
          width: Math.min(400, Math.max(200, Math.round(width))),
          locale: this.locale,
        },
        this.receive,
      );
      this.revealWhenSettled(slot);
    } catch {
      this.unavailable.set(true);
    }
  }

  /** Google shifts its frame once more after loading, so the button fades in after that. */
  private revealWhenSettled(slot: HTMLElement): void {
    const frame = slot.querySelector('iframe');
    const reveal = (): void => this.settled.set(true);
    if (!frame) {
      reveal();
      return;
    }
    const fallback = setTimeout(reveal, 2000);
    frame.addEventListener(
      'load',
      () => {
        clearTimeout(fallback);
        setTimeout(reveal, 300);
      },
      { once: true },
    );
  }
}
