import { HttpClient, HttpContext } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../../environments/environment';
import {
  SILENT_ERROR_CONTEXT,
  SILENT_ERROR_HANDLER,
  SKIP_AUTH_RETRY,
} from '../../../core/interceptors';
import { EmailChangeDto } from '../dto/email-change.dto';
import { LoginDto } from '../dto/login.dto';
import { PasswordChangeDto } from '../dto/password-change.dto';
import { PasswordResetRequestDto } from '../dto/password-reset-request.dto';
import { PasswordResetDto } from '../dto/password-reset.dto';
import { ProfileDto } from '../dto/profile.dto';
import { RegisterDto } from '../dto/register.dto';
import { SessionDto } from '../dto/session.dto';
import { UserDto } from '../dto/user.dto';
import { VerifyEmailDto } from '../dto/verify-email.dto';

/**
 * The signed-in account, if there is one — accounts are optional. The access
 * token is held in memory, the durable half of the session is the httpOnly
 * refresh cookie.
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

  /** Rename the account. The answer is what the server stored, so the cached
   * user adopts its reading rather than the optimistic one. Unlike the calls
   * around it this is an ordinary authenticated request: a 401 here is an
   * expired token and should be retried, not an answer. */
  async updateProfile(profile: ProfileDto): Promise<void> {
    this._user.set(
      await firstValueFrom(
        this.http.put<UserDto>(`${this.baseUrl}/me`, profile, {
          context: SILENT_ERROR_CONTEXT,
        }),
      ),
    );
  }

  /** The server signs out every device and answers with a fresh session for this one. */
  async changePassword(change: PasswordChangeDto): Promise<void> {
    this.adopt(
      await firstValueFrom(
        this.http.put<SessionDto>(`${this.baseUrl}/me/password`, change, {
          withCredentials: true,
          context: SILENT_ERROR_CONTEXT,
        }),
      ),
    );
  }

  /** Mails a link to the new address; the account keeps the old one until it is opened. */
  async requestEmailChange(change: EmailChangeDto): Promise<void> {
    await firstValueFrom(
      this.http.put<void>(`${this.baseUrl}/me/email`, change, { context: SILENT_ERROR_CONTEXT }),
    );
  }

  async verifyEmail(token: string): Promise<void> {
    await this.redeemMailLink('verify-email', token);
  }

  async confirmEmailChange(token: string): Promise<void> {
    await this.redeemMailLink('email-change/confirm', token);
  }

  /** The signed-in account adopts the result if the link was issued for it. */
  private async redeemMailLink(path: string, token: string): Promise<void> {
    await this.ready;
    const body: VerifyEmailDto = { token };
    const updated = await this.post<UserDto>(path, body);
    if (this._user()?.id === updated.id) {
      this._user.set(updated);
    }
  }

  async resendVerification(): Promise<void> {
    await firstValueFrom(
      this.http.post<void>(`${this.baseUrl}/verify-email/resend`, {}, {
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  async requestPasswordReset(request: PasswordResetRequestDto): Promise<void> {
    await this.post<void>('password-reset', request);
  }

  /** The server ends every session of the account, this one included. */
  async resetPassword(reset: PasswordResetDto): Promise<void> {
    await this.post<void>('password-reset/confirm', reset);
    this.clear();
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
