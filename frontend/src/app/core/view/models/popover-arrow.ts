import { Popover } from 'primeng/popover';

/** The views' side padding (rem) a popover keeps to the screen edge. */
const GUTTER = 1.5;

/** Keeps a popover within the views' side padding and puts its arrow under the middle of
 * `target`, the element it opened from. */
export function centrePopoverArrow(
  popover: Popover,
  target = popover.target as HTMLElement | null,
): void {
  const container = popover.container;
  if (!container || !target) {
    return;
  }
  keepInGutter(container);
  // offsetLeft ignores the opening animation's scale, which skews bounding rects.
  const rect = target.getBoundingClientRect();
  const scrollX = target.ownerDocument.defaultView?.scrollX ?? 0;
  const left = rect.left + scrollX + rect.width / 2 - container.offsetLeft;
  container.style.setProperty('--p-popover-arrow-left', `${left}px`);
  container.style.setProperty('--p-popover-arrow-offset', '0px');
}

/** Moves the panel sideways until it clears the gutter on both sides, centred if it cannot. */
function keepInGutter(container: HTMLElement): void {
  const view = container.ownerDocument.defaultView;
  if (!view) {
    return;
  }
  const rem = parseFloat(view.getComputedStyle(container.ownerDocument.documentElement).fontSize);
  const gutter = GUTTER * rem;
  const least = view.scrollX + gutter;
  const most = view.scrollX + view.innerWidth - gutter - container.offsetWidth;
  const left =
    most < least
      ? view.scrollX + (view.innerWidth - container.offsetWidth) / 2
      : Math.min(Math.max(container.offsetLeft, least), most);
  container.style.insetInlineStart = `${left}px`;
}
