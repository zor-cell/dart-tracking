import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { outputFromObservable } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { AutoFocus } from 'primeng/autofocus';
import { Button } from 'primeng/button';
import { Chip } from 'primeng/chip';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { Popover } from 'primeng/popover';
import { debounceTime, distinctUntilChanged, map } from 'rxjs';
import { FilterChip, FilterChipOpen, FilterSuggestion } from '../../models/filter-chip';
import { centrePopoverArrow } from '../../models/popover-arrow';

/** Above a list: the active filters and suggestions in one scrolling row, a search
 * that opens from its icon, a filter popover around the projected fields, and an
 * optional `listToolbarAction` button set slightly apart at the end. */
@Component({
  selector: 'app-list-toolbar',
  imports: [AutoFocus, Button, Chip, IconField, InputIcon, InputText, Popover, ReactiveFormsModule],
  templateUrl: './list-toolbar.component.html',
  styleUrl: './list-toolbar.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ListToolbarComponent {
  /** Placeholder of the search field; without it there is no search. */
  readonly searchLabel = input<string | null>(null);
  /** Shows the filter button when set. */
  readonly filterable = input(false);
  readonly chips = input<readonly FilterChip[]>([]);
  readonly suggestions = input<readonly FilterSuggestion[]>([]);
  /** Filters the popover can clear; fixed chips are not among them. */
  protected readonly removableCount = computed(
    () => this.chips().filter((chip) => chip.removable !== false).length,
  );

  readonly chipRemove = output<string>();
  readonly chipOpen = output<FilterChipOpen>();
  readonly suggestionPick = output<FilterSuggestion>();
  readonly reset = output<void>();

  protected readonly searching = signal(false);
  protected readonly query = new FormControl('', { nonNullable: true });
  readonly search = outputFromObservable(
    this.query.valueChanges.pipe(
      map((value) => value.trim()),
      debounceTime(250),
      distinctUntilChanged(),
    ),
  );

  private readonly filterButton = viewChild('filterButton', { read: ElementRef });
  private readonly panel = viewChild(Popover);

  protected togglePanel(event: Event): void {
    this.panel()?.toggle(event);
  }

  /** Closing the search drops what was typed, so the list never hides a query. */
  protected closeSearch(): void {
    this.query.setValue('');
    this.searching.set(false);
  }

  /** Puts the popover's arrow under the middle of the filter button. */
  protected centreArrow(): void {
    const panel = this.panel();
    const button = this.filterButton()?.nativeElement as HTMLElement | undefined;
    if (panel && button) {
      centrePopoverArrow(panel, button);
    }
  }
}
