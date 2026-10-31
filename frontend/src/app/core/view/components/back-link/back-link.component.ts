import { Location } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { backLabel } from '../../models/back-state';

/** The back link above a view title, labelled with where it leads: the page that opened the
 * view when it passed a `backState`, else `link`. */
@Component({
  selector: 'app-back-link',
  imports: [Button, RouterLink],
  templateUrl: './back-link.component.html',
  styleUrl: './back-link.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'view__back' },
})
export class BackLinkComponent {
  private readonly location = inject(Location);

  readonly label = input.required<string>();
  readonly link = input.required<string>();

  /** The opener's name; going back returns to it as it was left. */
  protected readonly opener = backLabel(this.location.getState());
  protected readonly shownLabel = computed(() => this.opener ?? this.label());

  protected back(): void {
    this.location.back();
  }
}
