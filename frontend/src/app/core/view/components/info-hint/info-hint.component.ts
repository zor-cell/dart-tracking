import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { Button } from 'primeng/button';
import { Popover } from 'primeng/popover';
import { centrePopoverArrow } from '../../models/popover-arrow';

/** Least gap between the popover and the screen's left edge, in pixels. */
const EDGE_GAP = 16;

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
  readonly label = input('Erklärung');

  /** Keeps the popover off the screen's edge, then points the arrow at the button. */
  protected place(popover: Popover): void {
    const container = popover.container;
    if (container && container.offsetLeft < EDGE_GAP) {
      container.style.left = `${EDGE_GAP}px`;
    }
    centrePopoverArrow(popover);
  }
}
