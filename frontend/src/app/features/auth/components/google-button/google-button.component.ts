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
import { ThemeService } from '../../../../core/theme/services/theme.service';

/** Height of the slot in px: the large button Google draws, without its frame's focus margin. */
const SLOT_HEIGHT = 40;

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
  private readonly theme = inject(ThemeService);
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
    const dark = this.theme.dark();
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

  /** Google draws a stand-in above its frame and drops it once the frame is ready;
   * the button fades in when only the frame is left. */
  private revealWhenSettled(slot: HTMLElement): void {
    const started = Date.now();
    const check = setInterval(() => {
      const frame = slot.querySelector('iframe');
      const height = slot.firstElementChild?.getBoundingClientRect().height ?? 0;
      const ready = frame !== null && frame.offsetHeight > 0 && height <= SLOT_HEIGHT;
      if (ready || Date.now() - started > 4000) {
        clearInterval(check);
        setTimeout(() => this.settled.set(true), 150);
      }
    }, 100);
  }
}
