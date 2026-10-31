import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** The compared player's name and value in grey, under one's own figure; a long name gives
 * way first, the value never. */
@Component({
  selector: 'app-compared-value',
  imports: [DecimalPipe],
  templateUrl: './compared-value.component.html',
  styleUrl: './compared-value.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ComparedValueComponent {
  readonly other = input.required<number | null>();
  readonly name = input.required<string>();
  /** Writes the name before the value; where the column already says whose it is, only for
   * screen readers. */
  readonly named = input(true);
  /** Decimals the value is shown with. */
  readonly digits = input(1);
  readonly unit = input('');

  protected readonly format = computed(() => `1.${this.digits()}-${this.digits()}`);
}
