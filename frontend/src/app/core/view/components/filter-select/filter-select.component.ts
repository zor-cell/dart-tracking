import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MultiSelect } from 'primeng/multiselect';

/** A labelled filter of a `list-filters` popover that takes any of several values. */
@Component({
  selector: 'app-filter-select',
  imports: [MultiSelect, ReactiveFormsModule],
  templateUrl: './filter-select.component.html',
  styleUrl: './filter-select.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FilterSelectComponent {
  readonly control = input.required<FormControl<unknown[]>>();
  readonly label = input.required<string>();
  readonly inputId = input.required<string>();
  readonly options = input.required<object[]>();
  readonly optionLabel = input('label');
  readonly optionValue = input('value');
  readonly placeholder = input($localize`:@@player.list.all:Alle`);
  /** Placeholder of a search over the options; without one the list has no search. */
  readonly searchLabel = input<string | null>(null);
}
