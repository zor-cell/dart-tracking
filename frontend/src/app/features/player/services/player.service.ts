import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { PlayerIdentityDto } from '../dto/player-identity.dto';
import { PlayerNameDto } from '../dto/player-name.dto';

/** Upper bound for the full address book, matching the server's maximum. */
const ADDRESS_BOOK_LIMIT = 500;

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

  /** The whole address book, own entry first. */
  list(): Promise<PlayerIdentityDto[]> {
    return firstValueFrom(
      this.http.get<PlayerIdentityDto[]>(this.baseUrl, {
        params: new HttpParams().set('limit', ADDRESS_BOOK_LIMIT),
      }),
    );
  }

  /** Rejects with a 409 when the address book already holds the name. */
  create(name: string): Promise<PlayerIdentityDto> {
    const body: PlayerNameDto = { name };
    return firstValueFrom(
      this.http.post<PlayerIdentityDto>(this.baseUrl, body, { context: SILENT_ERROR_CONTEXT }),
    );
  }

  rename(id: string, name: string): Promise<PlayerIdentityDto> {
    const body: PlayerNameDto = { name };
    return firstValueFrom(
      this.http.put<PlayerIdentityDto>(`${this.baseUrl}/${id}`, body, {
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  /** Take a player out of the address book; past games keep the name. */
  remove(id: string): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.baseUrl}/${id}`));
  }
}
