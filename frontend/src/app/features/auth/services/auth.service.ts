import { HttpClient, HttpContext } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { SILENT_ERROR_HANDLER, SKIP_AUTH_RETRY } from '../../../core/interceptors';
import { LoginDto } from '../dto/login.dto';
import { RegisterDto } from '../dto/register.dto';
import { SessionDto } from '../dto/session.dto';
import { UserDto } from '../dto/user.dto';

/**
 * The signed-in account, if there is one — accounts are optional. The access
 * token is held in memory, the durable half of the session is the httpOnly
 * refresh cookie (docs/feature/done/persistenz.md §8.4).
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.httpApiUrl}/auth`;

  private readonly _user = signal<UserDto | null>(null);
  private readonly _accessToken = signal<string | null>(null);
  private pending: Promise<string | null> | null = null;
  private restoring: Promise<void> | null = null;

  readonly user = this._user.asReadonly();
  readonly accessToken = this._accessToken.asReadonly();
  readonly isAuthenticated = computed(() => this._user() !== null);
  readonly isAdmin = computed(() => this._user()?.role === 'admin');

  /** Resolves once the cookie has been traded for a session, or found absent.
   * Started on first read, not in the constructor: the call runs through the
   * interceptor, which injects this service — mid-construction that is a cycle. */
  get ready(): Promise<void> {
    this.restoring ??= this.refresh().then(() => undefined);
    return this.restoring;
  }

  async login(credentials: LoginDto): Promise<void> {
    this.adopt(await this.post<SessionDto>('login', credentials));
  }

  async register(registration: RegisterDto): Promise<void> {
    this.adopt(await this.post<SessionDto>('register', registration));
  }

  async logout(): Promise<void> {
    try {
      await this.post<void>('logout', {});
    } finally {
      // The server-side session is gone either way; a failed call must not
      // leave this device looking signed in.
      this.clear();
    }
  }

  /** Swap the refresh cookie for a new access token, or clear the session.
   * Concurrent callers share one call — the server rotates the token on use, so
   * a second parallel refresh would redeem a spent one. */
  refresh(): Promise<string | null> {
    this.pending ??= this.requestRefresh().finally(() => {
      this.pending = null;
    });
    return this.pending;
  }

  private async requestRefresh(): Promise<string | null> {
    try {
      const session = await this.post<SessionDto>('refresh', {});
      this.adopt(session);
      return session.accessToken;
    } catch {
      this.clear();
      return null;
    }
  }

  /** Every auth call carries the cookie and reports its own failures. */
  private post<T>(path: string, body: unknown): Promise<T> {
    return firstValueFrom(
      this.http.post<T>(`${this.baseUrl}/${path}`, body, {
        withCredentials: true,
        context: new HttpContext()
          .set(SILENT_ERROR_HANDLER, true)
          .set(SKIP_AUTH_RETRY, true),
      }),
    );
  }

  private adopt(session: SessionDto): void {
    this._accessToken.set(session.accessToken);
    this._user.set(session.user);
  }

  private clear(): void {
    this._accessToken.set(null);
    this._user.set(null);
  }
}
