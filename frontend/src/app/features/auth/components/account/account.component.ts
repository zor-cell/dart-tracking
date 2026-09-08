import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { ProgressSpinner } from 'primeng/progressspinner';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-account',
  imports: [Button, DatePipe, ProgressSpinner, RouterLink],
  templateUrl: './account.component.html',
  styleUrl: './account.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AccountComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly user = this.auth.user;
  protected readonly isAdmin = this.auth.isAdmin;
  protected readonly busy = signal(false);
  protected readonly restoring = signal(true);

  constructor() {
    // This page is what it shows: everything on it hangs off `user()`, and
    // nothing else on this route asks for the session to be restored first.
    void this.auth.ready.then(() => this.restoring.set(false));
  }

  protected async logout(): Promise<void> {
    this.busy.set(true);
    try {
      await this.auth.logout();
      await this.router.navigateByUrl('/start');
    } finally {
      this.busy.set(false);
    }
  }
}
