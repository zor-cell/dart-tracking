import { DestroyRef, Directive, inject, output } from '@angular/core';

/** A held pointer waits this long (ms) before it repeats, then repeats faster down to the floor. */
const HOLD_DELAY = 500;
const FIRST_REPEAT = 120;
const FASTEST_REPEAT = 25;

/** A step button that can be held: a pointer presses once on its way down and keeps pressing
 * faster while it stays down, a keyboard click presses once. Holding selects no text. */
@Directive({
  selector: '[appRepeatPress]',
  host: {
    style: 'user-select: none; -webkit-user-select: none; -webkit-touch-callout: none',
    '(pointerdown)': 'start($event)',
    '(pointerup)': 'stop()',
    '(pointercancel)': 'stop()',
    '(document:pointerup)': 'stop()',
    '(document:pointercancel)': 'stop()',
    '(click)': 'click($event)',
  },
})
export class RepeatPressDirective {
  readonly appRepeatPress = output<void>();

  private timer: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.stop());
  }

  protected start(event: PointerEvent): void {
    if (event.button !== 0) {
      return;
    }
    this.stop();
    this.appRepeatPress.emit();
    const next = (delay: number, after: number) => {
      this.timer = setTimeout(() => {
        this.appRepeatPress.emit();
        next(after, Math.max(FASTEST_REPEAT, after * 0.85));
      }, delay);
    };
    next(HOLD_DELAY, FIRST_REPEAT);
  }

  protected stop(): void {
    clearTimeout(this.timer);
    this.timer = undefined;
  }

  /** Only a click from the keyboard presses; a pointer has already pressed on its way down. */
  protected click(event: MouseEvent): void {
    if (event.detail === 0) {
      this.appRepeatPress.emit();
    }
  }
}
