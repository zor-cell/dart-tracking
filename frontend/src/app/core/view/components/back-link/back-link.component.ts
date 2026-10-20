import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Button } from 'primeng/button';

/** The back link above a view title, labelled with where it leads. */
@Component({
  selector: 'app-back-link',
  imports: [Button, RouterLink],
  templateUrl: './back-link.component.html',
  styleUrl: './back-link.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'view__back' },
})
export class BackLinkComponent {
  readonly label = input.required<string>();
  readonly link = input.required<string>();
}
