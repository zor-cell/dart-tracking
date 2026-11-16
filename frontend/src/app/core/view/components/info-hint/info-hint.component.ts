import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { Button } from 'primeng/button';
import { Popover } from 'primeng/popover';
import { centrePopoverArrow } from '../../models/popover-arrow';

/** Least gap between the popover and the screen's edges, in pixels. */
const EDGE_GAP = 16;
/** Widest a wide popover grows on a large screen, in pixels. */
const WIDE_MAX = 416;

/** An info button that opens the projected explanation in a popover. */
@Component({
  selector: 'app-info-hint',
  imports: [Button, Popover],
  templateUrl: './info-hint.component.html',
  styleUrl: './info-hint.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InfoHintComponent {
  /** What the button is called for screen readers. */
  readonly label = input($localize`:@@common.explanation:Erklärung`);
  /** Whether the popover takes the screen's width on a phone, for content wider than a hint. */
  readonly wide = input(false);

  /** Keeps the popover off the screen's edges, then points the arrow at the button. */
  protected place(popover: Popover): void {
    const container = popover.container;
    if (!container) {
      return;
    }
    const screen = container.ownerDocument.documentElement.clientWidth;
    if (this.wide()) {
      const width = Math.min(screen - 2 * EDGE_GAP, WIDE_MAX);
      container.style.width = `${width}px`;
      const left = Math.min(container.offsetLeft, screen - EDGE_GAP - width);
      container.style.left = `${Math.max(left, EDGE_GAP)}px`;
    } else if (container.offsetLeft < EDGE_GAP) {
      container.style.left = `${EDGE_GAP}px`;
    }
    centrePopoverArrow(popover);
  }
}
