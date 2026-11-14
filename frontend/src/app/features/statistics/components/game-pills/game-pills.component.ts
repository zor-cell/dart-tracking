import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterRenderEffect,
  computed,
  inject,
  input,
  model,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SelectButton } from 'primeng/selectbutton';

/** The games a view shows figures for, as a toggle in one line that scrolls sideways. */
@Component({
  selector: 'app-game-pills',
  imports: [FormsModule, SelectButton],
  templateUrl: './game-pills.component.html',
  styleUrl: './game-pills.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GamePillsComponent<T extends string> {
  private readonly host: ElementRef<HTMLElement> = inject(ElementRef);

  readonly options = input.required<readonly { label: string; value: T }[]>();
  /** The same options as the toggle takes them. */
  protected readonly choices = computed(() => [...this.options()]);
  readonly game = model.required<T>();
  readonly ariaLabel = input.required<string>();

  constructor() {
    // Keeps the picked game in view when the row is wider than the screen.
    afterRenderEffect(() => {
      this.game();
      this.host.nativeElement
        .querySelector('.p-togglebutton-checked')
        ?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    });
  }
}
