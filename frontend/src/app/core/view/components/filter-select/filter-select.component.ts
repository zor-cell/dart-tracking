import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { Select } from 'primeng/select';
import { startWith, switchMap } from 'rxjs';
import { orList } from '../../models/filter-chip';

/** A labelled filter of a `list-filters` popover that takes any of several values. */
@Component({
  selector: 'app-filter-select',
  imports: [Select, ReactiveFormsModule],
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

  private readonly picks = toSignal(
    toObservable(this.control).pipe(
      switchMap((control) => control.valueChanges.pipe(startWith(control.value))),
    ),
    { initialValue: [] },
  );

  protected readonly pickedLabel = computed(() => {
    const picks = this.picks() ?? [];
    const field = (option: object, key: string) => (option as Record<string, unknown>)[key];
    return orList(
      this.options()
        .filter((option) => picks.includes(field(option, this.optionValue())))
        .map((option) => String(field(option, this.optionLabel()))),
    );
  });
}
