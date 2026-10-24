import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { outputFromObservable } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { Chip } from 'primeng/chip';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { Popover } from 'primeng/popover';
import { debounceTime, distinctUntilChanged, map } from 'rxjs';
import { FilterChip } from '../../models/filter-chip';

/** Above a list: search, a filter popover around the projected fields and the active
 * filters as chips. The number of matches sits in the table's paginator. */
@Component({
  selector: 'app-list-toolbar',
  imports: [Button, Chip, IconField, InputIcon, InputText, Popover, ReactiveFormsModule],
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

  readonly chipRemove = output<string>();
  readonly reset = output<void>();

  protected readonly query = new FormControl('', { nonNullable: true });
  readonly search = outputFromObservable(
    this.query.valueChanges.pipe(
      map((value) => value.trim()),
      debounceTime(250),
      distinctUntilChanged(),
    ),
  );
}
