import {
  CdkDrag,
  CdkDragDrop,
  CdkDragHandle,
  CdkDragPlaceholder,
  CdkDragPreview,
  CdkDragStart,
  CdkDropList,
} from '@angular/cdk/drag-drop';
import { DOCUMENT, NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  TemplateRef,
  afterNextRender,
  contentChild,
  inject,
  input,
  output,
  signal,
} from '@angular/core';

/** An item that left `from` and now sits at `to`. */
export interface SortableMove {
  readonly from: number;
  readonly to: number;
}

/** Rows reordered by dragging their grip, or by arrow keys on it; the projected
 * template draws the rest of each row. */
@Component({
  selector: 'app-sortable-list',
  imports: [
    CdkDrag,
    CdkDragHandle,
    CdkDragPlaceholder,
    CdkDragPreview,
    CdkDropList,
    NgTemplateOutlet,
  ],
  templateUrl: './sortable-list.component.html',
  styleUrl: './sortable-list.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SortableListComponent<T> {
  private readonly document = inject(DOCUMENT);
  private readonly injector = inject(Injector);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly items = input.required<readonly T[]>();
  /** What a row is called: the dragged preview shows it, the grip's label names it. */
  readonly label = input.required<(item: T, index: number) => string>();

  protected readonly moveLabel = (name: string): string =>
    $localize`:@@common.sortable.move:${name}:name: verschieben, Pfeiltasten hoch und runter`;
  /** Rows in one bordered box with dividers, instead of spaced apart. */
  readonly bordered = input(false);

  readonly moved = output<SortableMove>();

  protected readonly row = contentChild.required(TemplateRef);
  /** Height of the row being dragged, in px, for its placeholder and its preview. */
  protected readonly placeholderHeight = signal(0);

  protected drop(event: CdkDragDrop<unknown>): void {
    if (event.previousIndex !== event.currentIndex) {
      this.moved.emit({ from: event.previousIndex, to: event.currentIndex });
    }
  }

  /** Slides the rows from where they are now to where the next render puts them. */
  animateReorder(): void {
    if (this.document.defaultView?.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }
    const rows = this.host.nativeElement.querySelectorAll<HTMLElement>(':scope > .sortable > .sortable__row');
    const before = new Map([...rows].map((row) => [row, row.getBoundingClientRect().top]));
    afterNextRender(
      () => {
        for (const [row, top] of before) {
          row.getAnimations().forEach((animation) => animation.cancel());
          const shift = top - row.getBoundingClientRect().top;
          if (shift !== 0) {
            row.animate([{ transform: `translateY(${shift}px)` }, { transform: 'none' }], {
              duration: 400,
              easing: 'cubic-bezier(0.2, 0, 0, 1)',
            });
          }
        }
      },
      { injector: this.injector },
    );
  }

  /** Closes the on-screen keyboard, so the viewport does not resize mid-drag. */
  protected started(event: CdkDragStart): void {
    this.placeholderHeight.set(event.source.element.nativeElement.offsetHeight);
    (this.document.activeElement as HTMLElement | null)?.blur();
  }

  /** Keyboard counterpart to dragging: arrow keys on the grip move the row by one. */
  protected step(event: Event, index: number, step: -1 | 1): void {
    event.preventDefault();
    const to = index + step;
    if (to < 0 || to >= this.items().length) {
      return;
    }
    const grip = event.target as HTMLElement;
    this.moved.emit({ from: index, to });
    afterNextRender(() => grip.focus(), { injector: this.injector });
  }
}
