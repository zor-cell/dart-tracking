import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { AbstractControl } from '@angular/forms';
import { startWith, switchMap } from 'rxjs';

/** The first rule a form control breaks, in German, once it was touched or edited. */
@Component({
  selector: 'app-field-error',
  templateUrl: './field-error.component.html',
  styleUrl: './field-error.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'field-error', 'aria-live': 'polite' },
})
export class FieldErrorComponent {
  readonly control = input.required<AbstractControl>();
  /** Texts per validator key that replace the defaults, e.g. `{ pattern: '…' }`. */
  readonly messages = input<Readonly<Record<string, string>>>({});

  private readonly changes = toSignal(
    toObservable(this.control).pipe(
      switchMap((control) => control.events.pipe(startWith(null))),
    ),
  );

  protected readonly message = computed(() => {
    this.changes();
    const control = this.control();
    if (control.errors === null || !(control.touched || control.dirty)) {
      return null;
    }
    const [key, detail] = Object.entries(control.errors)[0];
    return this.messages()[key] ?? defaultMessage(key, detail);
  });
}

function defaultMessage(key: string, detail: unknown): string {
  const length = (detail as { requiredLength?: number }).requiredLength;
  switch (key) {
    case 'required':
      return 'Bitte ausfüllen.';
    case 'email':
      return 'Bitte eine gültige E-Mail-Adresse eingeben.';
    case 'minlength':
      return `Mindestens ${length} Zeichen.`;
    case 'maxlength':
      return `Höchstens ${length} Zeichen.`;
    default:
      return 'Ungültige Eingabe.';
  }
}
