import {
  afterRenderEffect,
  DestroyRef,
  Directive,
  ElementRef,
  inject,
  Injector,
  input,
} from '@angular/core';

/** How small the text may get before it is left to wrap after all, in px. */
const MIN_FONT_SIZE = 11;

/** Measuring passes; font metrics do not scale perfectly linearly. */
const MAX_PASSES = 3;

/**
 * Keeps a value on one line by shrinking it until it fits, down to
 * `MIN_FONT_SIZE`. Below that it wraps — put a `<wbr>` where the break belongs.
 *
 * The bound value is the text itself, so a change re-measures.
 */
@Directive({ selector: '[appFitText]' })
export class FitTextDirective {
  readonly appFitText = input.required<string>();

  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private readonly destroyRef = inject(DestroyRef);

  /** The size the element has without this directive. */
  private base = 0;
  private width = -1;

  constructor() {
    afterRenderEffect(() => {
      this.appFitText();
      this.fit();
    });

    // The room a row offers changes with the window, which no signal reports.
    afterRenderEffect(
      () => {
        const observer = new ResizeObserver(([entry]) => {
          if (entry.contentRect.width !== this.width) {
            this.width = entry.contentRect.width;
            this.fit();
          }
        });
        observer.observe(this.element.nativeElement);
        this.destroyRef.onDestroy(() => observer.disconnect());
      },
      { injector: this.injector },
    );
  }

  private fit(): void {
    const node = this.element.nativeElement;
    this.base ||= parseFloat(getComputedStyle(node).fontSize);

    let size = this.base;
    node.style.fontSize = `${size}px`;

    for (let pass = 0; pass < MAX_PASSES; pass++) {
      const available = node.clientWidth;
      const needed = this.textWidth();
      if (!available || !needed || needed <= available || size <= MIN_FONT_SIZE) {
        return;
      }
      size = Math.max((size * available) / needed, MIN_FONT_SIZE);
      node.style.fontSize = `${size}px`;
    }
  }

  /**
   * What the text needs on one line. Summed over the rectangles the content
   * occupies, so a line it has already broken into is measured as the whole —
   * the element's own width says nothing, it is as wide as the row gives it.
   */
  private textWidth(): number {
    const range = document.createRange();
    range.selectNodeContents(this.element.nativeElement);
    return [...range.getClientRects()].reduce((sum, rect) => sum + rect.width, 0);
  }
}
