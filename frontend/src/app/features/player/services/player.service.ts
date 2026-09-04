import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { PlayerIdentityDto } from '../dto/player-identity.dto';

/**
 * The people this account has played with. Requires a session — without one
 * there is no address book, and every name is typed fresh.
 */
@Injectable({ providedIn: 'root' })
export class PlayerService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.httpApiUrl}/players`;

  /** Identities whose name starts with `prefix`; the whole book if it is empty.
   * Resolves to an empty list when signed out, so callers need no special case. */
  async search(prefix: string): Promise<PlayerIdentityDto[]> {
    try {
      return await firstValueFrom(
        this.http.get<PlayerIdentityDto[]>(this.baseUrl, {
          params: new HttpParams().set('q', prefix),
          context: SILENT_ERROR_CONTEXT,
        }),
      );
    } catch {
      return [];
    }
  }
}
