import { ChangeDetectionStrategy, Component, ElementRef, inject, input, output } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { AutoFocus } from 'primeng/autofocus';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { FieldErrorComponent } from '../field-error/field-error.component';

let nextId = 0;

/** A value edited in place: input, save and cancel, its errors below. Escape and a
 * press outside cancel. */
@Component({
  selector: 'app-inline-editor',
  imports: [AutoFocus, Button, FieldErrorComponent, InputText, Message, ReactiveFormsModule],
  templateUrl: './inline-editor.component.html',
  styleUrl: './inline-editor.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  // pointerdown runs before the pressed button's click, so another row's pencil opens after this closes.
  host: { '(document:pointerdown)': 'onPointerDown($event)' },
})
export class InlineEditorComponent {
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly control = input.required<FormControl<string>>();
  /** Accessible name of the input. */
  readonly label = input.required<string>();
  readonly saveLabel = input('Speichern');
  readonly autocomplete = input('off');
  /** Texts per validator key, passed on to the field error. */
  readonly messages = input<Readonly<Record<string, string>>>({});
  readonly saving = input(false);
  /** The failed request's message, shown under the input. */
  readonly error = input<string | null>(null);

  readonly save = output<void>();
  readonly cancel = output<void>();

  protected readonly errorId = `inline-editor-error-${nextId++}`;

  protected onSubmit(event: Event): void {
    event.preventDefault();
    if (this.control().valid && !this.saving()) {
      this.save.emit();
    }
  }

  protected onPointerDown(event: Event): void {
    if (!this.saving() && !this.host.nativeElement.contains(event.target as Node | null)) {
      this.cancel.emit();
    }
  }

  protected onEscape(): void {
    if (!this.saving()) {
      this.cancel.emit();
    }
  }
}
