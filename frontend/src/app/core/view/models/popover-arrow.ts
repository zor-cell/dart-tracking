import { Popover } from 'primeng/popover';

/** Puts a popover's arrow under the middle of `target`, the element it opened from. */
export function centrePopoverArrow(
  popover: Popover,
  target = popover.target as HTMLElement | null,
): void {
  const container = popover.container;
  if (!container || !target) {
    return;
  }
  // offsetLeft ignores the opening animation's scale, which skews bounding rects.
  const rect = target.getBoundingClientRect();
  const scrollX = target.ownerDocument.defaultView?.scrollX ?? 0;
  const left = rect.left + scrollX + rect.width / 2 - container.offsetLeft;
  container.style.setProperty('--p-popover-arrow-left', `${left}px`);
  container.style.setProperty('--p-popover-arrow-offset', '0px');
}
