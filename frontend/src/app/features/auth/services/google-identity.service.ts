import { DOCUMENT } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { GoogleConfigDto } from '../dto/google-config.dto';
import { GoogleAccountsId, GoogleButtonOptions, GoogleWindow } from '../models/google-identity';

const SCRIPT_URL = 'https://accounts.google.com/gsi/client';

/** Loads Google's sign-in script once and routes its credential to the button shown last. */
@Injectable({ providedIn: 'root' })
export class GoogleIdentityService {
  private readonly document = inject(DOCUMENT);
  private readonly http = inject(HttpClient);
  private loading: Promise<GoogleAccountsId> | null = null;
  private receiver: ((credential: string) => void) | null = null;

  /** Draws Google's button into `parent`; `receiver` gets the ID token once the user picked an account. */
  async renderButton(
    parent: HTMLElement,
    options: GoogleButtonOptions,
    receiver: (credential: string) => void,
  ): Promise<void> {
    const accounts = await this.load();
    this.receiver = receiver;
    parent.replaceChildren();
    accounts.renderButton(parent, options);
  }

  release(receiver: (credential: string) => void): void {
    if (this.receiver === receiver) {
      this.receiver = null;
    }
  }

  private load(): Promise<GoogleAccountsId> {
    this.loading ??= Promise.all([this.clientId(), this.script()])
      .then(([clientId, accounts]) => {
        accounts.initialize({
          client_id: clientId,
          callback: ({ credential }) => this.receiver?.(credential),
          auto_select: false,
        });
        return accounts;
      })
      .catch((failure: unknown) => {
        this.loading = null;
        throw failure;
      });
    return this.loading;
  }

  private async clientId(): Promise<string> {
    const config = await firstValueFrom(
      this.http.get<GoogleConfigDto>(`${environment.httpApiUrl}/auth/google`, {
        context: SILENT_ERROR_CONTEXT,
      }),
    );
    return config.clientId;
  }

  private script(): Promise<GoogleAccountsId> {
    return new Promise<GoogleAccountsId>((resolve, reject) => {
      const script = this.document.createElement('script');
      script.src = SCRIPT_URL;
      script.async = true;
      script.onload = () => {
        const accounts = (this.document.defaultView as GoogleWindow | null)?.google?.accounts.id;
        if (accounts) {
          resolve(accounts);
        } else {
          reject(new Error('Google Identity Services did not load'));
        }
      };
      script.onerror = () => reject(new Error('Google Identity Services did not load'));
      this.document.head.appendChild(script);
    });
  }
}
