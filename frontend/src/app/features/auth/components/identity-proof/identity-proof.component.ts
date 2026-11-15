import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { ReactiveFormsModule } from '@angular/forms';
import { InputText } from 'primeng/inputtext';
import { FieldErrorComponent } from '../../../../core/view/components/field-error/field-error.component';
import { IdentityCheck } from '../../models/identity-check';
import { GoogleConfirmComponent } from '../google-confirm/google-confirm.component';

/** The password field of an `IdentityCheck`, or its Google confirmation instead. */
@Component({
  selector: 'app-identity-proof',
  imports: [ReactiveFormsModule, InputText, FieldErrorComponent, GoogleConfirmComponent],
  templateUrl: './identity-proof.component.html',
  styleUrl: './identity-proof.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class IdentityProofComponent {
  readonly check = input.required<IdentityCheck>();
  readonly inputId = input.required<string>();
  readonly label = input($localize`:@@auth.currentPassword:Aktuelles Passwort`);
  /** Further ids that describe the password field, such as a hint above it. */
  readonly describedBy = input('');
}
