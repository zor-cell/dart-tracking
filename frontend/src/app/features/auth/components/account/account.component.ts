import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Avatar } from 'primeng/avatar';
import { Button } from 'primeng/button';
import { APP_VERSION } from '../../../../../environments/version';
import { AuthService } from '../../services/auth.service';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { LanguageSelectComponent } from '../../../settings/components/language-select/language-select.component';

/** A row that opens another page of the account area. */
interface PageLink {
  readonly link: string;
  readonly icon: string;
  readonly label: string;
  readonly hint: string;
}

const OWN_PAGES: readonly PageLink[] = [
  {
    link: '/account/stats',
    icon: 'pi-chart-bar',
    label: $localize`:@@auth.account.stats:Statistik`,
    hint: $localize`:@@auth.account.statsHint:Average, Checkout, Trefferbild`,
  },
  {
    link: '/account/games',
    icon: 'pi-history',
    label: $localize`:@@auth.account.games:Spiele`,
    hint: $localize`:@@auth.account.gamesHint:Verlauf und Replays`,
  },
  {
    link: '/account/players',
    icon: 'pi-users',
    label: $localize`:@@auth.account.players:Spieler`,
    hint: $localize`:@@auth.account.playersHint:Für neue Spiele auswählbar`,
  },
];

const APP_PAGES: readonly PageLink[] = [
  {
    link: '/account/settings',
    icon: 'pi-cog',
    label: $localize`:@@auth.account.settings:Einstellungen`,
    hint: $localize`:@@auth.account.settingsHint:Sprache, Lieblingsdoppel, Ansage`,
  },
];

const ADMIN_PAGES: readonly PageLink[] = [
  {
    link: '/account/evaluation',
    icon: 'pi-bullseye',
    label: $localize`:@@auth.account.evaluation:Auswertung`,
    hint: $localize`:@@auth.account.evaluationHint:Genauigkeit der Erkennung`,
  },
];

@Component({
  selector: 'app-account',
  imports: [Avatar, Button, LanguageSelectComponent, LoadingStateComponent, RouterLink],
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
    { title: $localize`:@@auth.account.ownData:Meine Daten`, pages: OWN_PAGES },
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
