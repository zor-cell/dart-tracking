import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { Select } from 'primeng/select';
import { SelectButton } from 'primeng/selectbutton';
import { TrainingFieldDto } from '../../dto/training-settings.dto';
import { fieldLabel } from '../../models/variant-options';

/** The 25 and the 50 as entries of the number list; they have no ring to pick. */
const BULLS = [25, 50];

/** Picks the board fields a training is thrown at: the chosen ones, and a row that adds one. */
@Component({
  selector: 'app-field-picker',
  imports: [ReactiveFormsModule, Button, Select, SelectButton],
  templateUrl: './field-picker.component.html',
  styleUrl: './field-picker.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FieldPickerComponent {
  readonly fields = input.required<readonly TrainingFieldDto[]>();
  readonly fieldsChange = output<readonly TrainingFieldDto[]>();

  protected readonly rings = [
    { label: 'Single', value: 1 },
    { label: 'Double', value: 2 },
    { label: 'Triple', value: 3 },
  ];
  protected readonly numbers = [...Array.from({ length: 20 }, (_, index) => index + 1), ...BULLS].map(
    (value) => ({ label: `${value}`, value }),
  );

  protected readonly ring = new FormControl(1, { nonNullable: true });
  protected readonly number = new FormControl(20, { nonNullable: true });
  private readonly pickedRing = toSignal(this.ring.valueChanges, { initialValue: this.ring.value });
  private readonly pickedNumber = toSignal(this.number.valueChanges, { initialValue: this.number.value });

  protected readonly fieldLabel = fieldLabel;
  protected readonly removeLabel = (field: TrainingFieldDto): string =>
    $localize`:@@game.fields.remove:${fieldLabel(field)}:field: entfernen`;

  /** The field the add row names now. */
  private readonly picked = computed<TrainingFieldDto>(() => {
    const value = this.pickedNumber();
    return BULLS.includes(value)
      ? { value: 25, multiplier: value === 50 ? 2 : 1 }
      : { value, multiplier: this.pickedRing() };
  });

  /** Whether the named field can still be added: each one once. */
  protected readonly addable = computed(() => {
    const picked = this.picked();
    return !this.fields().some(
      (field) => field.value === picked.value && field.multiplier === picked.multiplier,
    );
  });

  constructor() {
    this.number.valueChanges.subscribe((value) =>
      BULLS.includes(value) ? this.ring.disable() : this.ring.enable(),
    );
  }

  protected add(): void {
    if (this.addable()) {
      this.fieldsChange.emit([...this.fields(), this.picked()]);
    }
  }

  protected remove(index: number): void {
    this.fieldsChange.emit(this.fields().filter((_, at) => at !== index));
  }
}
