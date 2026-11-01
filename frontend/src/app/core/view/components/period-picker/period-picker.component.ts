import { ChangeDetectionStrategy, Component, computed, input, model, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePicker } from 'primeng/datepicker';
import { Popover } from 'primeng/popover';
import { SelectButton } from 'primeng/selectbutton';
import { DayRange } from '../../models/day-range';
import { DEFAULT_PERIODS, PERIOD_UNITS, PERIODS, Period, PeriodUnit } from '../../models/period';

/** A popover with the period's quick picks and a calendar for a range of its own; with
 * `units`, the picks can also count back in games. */
@Component({
  selector: 'app-period-picker',
  imports: [DatePicker, FormsModule, Popover, SelectButton],
  templateUrl: './period-picker.component.html',
  styleUrl: './period-picker.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PeriodPickerComponent {
  readonly units = input(false);
  readonly unit = model<PeriodUnit>('days');
  readonly period = model.required<Period>();
  readonly range = model<DayRange>(null);

  protected readonly unitOptions = [...PERIOD_UNITS];
  protected readonly periodOptions = computed(() => [...PERIODS[this.unit()]]);

  private readonly popover = viewChild.required(Popover);

  /** Opens the picker under the tap, or closes it. */
  toggle(event: Event): void {
    this.popover().toggle(event);
  }

  /** Switch what the quick picks count; "all" stays, any other pick starts over. */
  protected selectUnit(unit: PeriodUnit): void {
    this.unit.set(unit);
    if (this.period() !== 'all') {
      this.period.set(DEFAULT_PERIODS[unit]);
    }
  }

  /** A quick pick closes the picker; the calendar pick opens the calendar in it instead. */
  protected selectPeriod(period: Period): void {
    this.period.set(period);
    if (period !== 'custom') {
      this.popover().hide();
    }
  }

  protected pickRange(range: DayRange): void {
    this.range.set(range);
    if (range?.[1]) {
      this.popover().hide();
    }
  }
}
