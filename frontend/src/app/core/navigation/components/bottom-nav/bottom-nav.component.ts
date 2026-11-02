import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { NavItem } from '../../models/nav-item';

@Component({
  selector: 'app-bottom-nav',
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './bottom-nav.component.html',
  styleUrl: './bottom-nav.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BottomNavComponent {
  protected readonly items: readonly NavItem[] = [
    { path: '/start', label: $localize`:@@common.nav.start:Start`, icon: 'pi-home' },
    { path: '/game', label: $localize`:@@common.nav.game:Spiel`, icon: 'pi-play-circle' },
    { path: '/account', label: $localize`:@@common.nav.account:Konto`, icon: 'pi-user' },
  ];
}
