import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Avatar } from 'primeng/avatar';
import { Button } from 'primeng/button';
import { APP_VERSION } from '../../../../../environments/version';
import { AuthService } from '../../services/auth.service';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';

/** A row that opens another page of the account area. */
interface PageLink {
  readonly link: string;
  readonly icon: string;
  readonly label: string;
  readonly hint: string;
}

const OWN_PAGES: readonly PageLink[] = [
  { link: '/account/stats', icon: 'pi-chart-bar', label: 'Statistik', hint: 'Average, Checkout, Trefferbild' },
  { link: '/account/games', icon: 'pi-history', label: 'Spiele', hint: 'Verlauf und Replays' },
  { link: '/account/players', icon: 'pi-users', label: 'Spieler', hint: 'Für neue Spiele auswählbar' },
];

const APP_PAGES: readonly PageLink[] = [
  { link: '/account/settings', icon: 'pi-cog', label: 'Einstellungen', hint: 'Eingabe, Lieblingsdoppel, Ansage' },
];

const ADMIN_PAGES: readonly PageLink[] = [
  { link: '/account/evaluation', icon: 'pi-bullseye', label: 'Auswertung', hint: 'Genauigkeit der Erkennung' },
];

@Component({
  selector: 'app-account',
  imports: [Avatar, Button, LoadingStateComponent, RouterLink],
  templateUrl: './account.component.html',
  styleUrl: './account.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AccountComponent {
  private readonly auth = inject(AuthService);

  protected readonly user = this.auth.user;
  protected readonly restoring = signal(true);
  protected readonly version = APP_VERSION;

  protected readonly groups = computed(() => [
    { title: 'Meine Daten', pages: OWN_PAGES },
    { title: 'App', pages: APP_PAGES },
    ...(this.auth.isAdmin() ? [{ title: 'Admin', pages: ADMIN_PAGES }] : []),
  ]);

  /** Up to two initials from the display name, for the avatar. */
  protected readonly initials = computed(() =>
    (this.user()?.displayName ?? '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((word) => word[0].toUpperCase())
      .join(''),
  );

  constructor() {
    // This page is what it shows: everything on it hangs off `user()`, and
    // nothing else on this route asks for the session to be restored first.
    void this.auth.ready.then(() => this.restoring.set(false));
  }
}
