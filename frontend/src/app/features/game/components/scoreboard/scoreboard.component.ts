import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  input,
  viewChild,
} from '@angular/core';
import { Skeleton } from 'primeng/skeleton';
import { ScoreboardEntry } from '../../models/scoreboard-entry';

/** A row of player cards that keeps the active one centred; null entries draw placeholders. */
@Component({
  selector: 'app-scoreboard',
  imports: [Skeleton],
  templateUrl: './scoreboard.component.html',
  styleUrl: './scoreboard.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ScoreboardComponent {
  readonly entries = input.required<readonly ScoreboardEntry[] | null>();
  readonly activeIndex = input<number | null>(null);
  readonly winnerId = input<number | null>(null);

  private readonly listRef = viewChild<ElementRef<HTMLUListElement>>('list');

  /** A Cricket target's marks as drawn on a chalk board: none, slash, cross, circled cross. */
  protected readonly glyphs = ['', '/', '✕', 'ⓧ'];

  /** Placeholder cards while the state is on its way: two, the smallest game. */
  protected readonly skeletonEntries = [0, 1];

  /**
   * How many player cards share the row's width. Up to three, so the thrower
   * keeps a neighbour on each side; beyond that the row scrolls.
   */
  protected readonly visibleCards = computed(() => Math.min(this.entries()?.length ?? 2, 3));

  // Who was reset as of the last state; null until the first, so a reload does
  // not jump to an old reset.
  private resetIds: ReadonlySet<number> | null = null;

  constructor() {
    // Follow play along the row, so the thrower stays in the middle and the two
    // around them stay in view. A no-op while everyone fits.
    effect(() => {
      const index = this.activeIndex();
      const list = this.listRef()?.nativeElement;
      if (list !== undefined && index !== null) {
        centre(list, index);
      }
    });

    // Turn to a player the moment they are sent back to zero; the next handover
    // brings the row back to the thrower.
    effect(() => {
      const entries = this.entries();
      const list = this.listRef()?.nativeElement;
      if (entries === null || list === undefined) {
        return;
      }
      const before = this.resetIds;
      this.resetIds = new Set(entries.filter((entry) => entry.reset).map((entry) => entry.id));
      const fresh = entries.findIndex((entry) => entry.reset && before !== null && !before.has(entry.id));
      if (fresh !== -1) {
        centre(list, fresh);
      }
    });
  }
}

/** Scroll the row so the card at `index` sits in the middle. */
function centre(list: HTMLElement, index: number): void {
  const card = list.children.item(index) as HTMLElement | null;
  if (card !== null) {
    list.scrollTo({ left: card.offsetLeft + card.offsetWidth / 2 - list.clientWidth / 2 });
  }
}
