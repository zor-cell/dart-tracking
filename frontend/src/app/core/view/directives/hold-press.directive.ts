import { DestroyRef, Directive, ElementRef, inject, input, output, signal } from '@angular/core';

/** A button that does something else when held: a pointer or Space kept down for
 * `holdMs` emits once, and the click that ends that press is swallowed. */
@Directive({
  selector: '[appHoldPress]',
  host: {
    style: 'user-select: none; -webkit-user-select: none; -webkit-touch-callout: none',
    '[class.hold-press--charging]': 'charging()',
    '[style.--hold-ms]': "holdMs() + 'ms'",
    '(pointerdown)': 'start($event)',
    '(pointerup)': 'stop()',
    '(pointercancel)': 'stop()',
    '(pointerleave)': 'stop()',
    '(keydown)': 'keyDown($event)',
    '(keyup)': 'stop()',
    '(contextmenu)': 'holdEnabled() && $event.preventDefault()',
  },
})
export class HoldPressDirective {
  readonly holdMs = input(800);
  /** Whether holding does anything; off, the button is an ordinary one. */
  readonly holdEnabled = input(true);
  readonly appHoldPress = output<void>();

  /** Whether a press is under way and still short of the hold. */
  protected readonly charging = signal(false);

  private timer: ReturnType<typeof setTimeout> | undefined;
  private held = false;

  constructor() {
    const host = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
    const swallow = (event: Event) => {
      if (this.held) {
        this.held = false;
        event.stopPropagation();
        event.preventDefault();
      }
    };
    host.addEventListener('click', swallow, { capture: true });
    inject(DestroyRef).onDestroy(() => {
      this.stop();
      host.removeEventListener('click', swallow, { capture: true });
    });
  }

  protected start(event: PointerEvent): void {
    if (event.button === 0) {
      this.begin();
    }
  }

  /** Space clicks on release, so it can be held; Enter clicks at once and stays a tap. */
  protected keyDown(event: KeyboardEvent): void {
    if (event.key === ' ' && !event.repeat) {
      this.begin();
    } else if (event.key === 'Enter') {
      this.held = false;
    }
  }

  protected stop(): void {
    clearTimeout(this.timer);
    this.timer = undefined;
    this.charging.set(false);
  }

  private begin(): void {
    this.stop();
    this.held = false;
    if (!this.holdEnabled()) {
      return;
    }
    this.charging.set(true);
    this.timer = setTimeout(() => {
      this.timer = undefined;
      this.charging.set(false);
      this.held = true;
      this.appHoldPress.emit();
    }, this.holdMs());
  }
}
