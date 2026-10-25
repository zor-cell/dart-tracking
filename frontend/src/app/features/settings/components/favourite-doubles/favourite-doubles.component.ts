import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { Select, SelectChangeEvent } from 'primeng/select';
import {
  SortableListComponent,
  SortableMove,
} from '../../../../core/view/components/sortable-list/sortable-list.component';

/** The finishing doubles a player can prefer, by sector (25 for the bull), as the checkout labels them. */
const DOUBLE_OPTIONS = [
  ...Array.from({ length: 20 }, (_, i) => ({ label: `D${20 - i}`, value: 20 - i })),
  { label: 'Double Bull', value: 25 },
];

/** The player's favourite doubles as a ranked list: first is tried first. */
@Component({
  selector: 'app-favourite-doubles',
  imports: [Button, ReactiveFormsModule, Select, SortableListComponent],
  templateUrl: './favourite-doubles.component.html',
  styleUrl: './favourite-doubles.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FavouriteDoublesComponent {
  readonly doubles = input.required<readonly number[]>();
  readonly doublesChange = output<number[]>();

  /** The doubles not on the list yet. */
  protected readonly options = computed(() =>
    DOUBLE_OPTIONS.filter((option) => !this.doubles().includes(option.value)),
  );

  /** The picker below the list; it empties again once a double is added. */
  protected readonly adding = new FormControl<number | null>(null);

  protected readonly name = (double: number): string =>
    DOUBLE_OPTIONS.find((option) => option.value === double)?.label ?? `D${double}`;

  /** Appends the picked double and empties the picker again. */
  protected add({ value }: SelectChangeEvent): void {
    if (value !== null) {
      this.doublesChange.emit([...this.doubles(), value]);
      this.adding.setValue(null);
    }
  }

  protected move({ from, to }: SortableMove): void {
    const doubles = [...this.doubles()];
    doubles.splice(to, 0, ...doubles.splice(from, 1));
    this.doublesChange.emit(doubles);
  }

  protected remove(index: number): void {
    this.doublesChange.emit(this.doubles().filter((_, other) => other !== index));
  }
}
