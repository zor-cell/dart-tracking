import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { InvitationAcceptanceDto } from '../dto/invitation-acceptance.dto';
import { InvitationDto } from '../dto/invitation.dto';
import { InviteLinkDto } from '../dto/invite-link.dto';
import { PlayerIdentityDto } from '../dto/player-identity.dto';
import { PlayerLinkDto } from '../dto/player-link.dto';
import { PlayerNameDto } from '../dto/player-name.dto';
import { PlayerPageDto } from '../dto/player-page.dto';

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

  /** One page of the address book, own entry first; failures are left to the caller. */
  page(limit: number, offset: number): Promise<PlayerPageDto> {
    return firstValueFrom(
      this.http.get<PlayerPageDto>(`${this.baseUrl}/page`, {
        params: new HttpParams().set('limit', limit).set('offset', offset),
        context: SILENT_ERROR_CONTEXT,
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

  /** A fresh invitation for an unlinked player; it voids the previous one. */
  invite(id: string): Promise<InviteLinkDto> {
    return firstValueFrom(this.http.post<InviteLinkDto>(`${this.baseUrl}/${id}/invitation`, null));
  }

  /** Detach a player from its account, which keeps the past games. Resolves to the
   * entry that now stands in the address book, a new one if there were games. */
  unlink(id: string): Promise<PlayerIdentityDto> {
    return firstValueFrom(this.http.delete<PlayerIdentityDto>(`${this.baseUrl}/${id}/link`));
  }

  /** Where this account is linked in someone else's address book. */
  links(): Promise<PlayerLinkDto[]> {
    return firstValueFrom(this.http.get<PlayerLinkDto[]>(`${this.baseUrl}/links`));
  }

  /** Undo a link to this account; `keepHistory` keeps the games played so far. */
  leave(playerId: string, keepHistory: boolean): Promise<void> {
    return firstValueFrom(
      this.http.delete<void>(`${this.baseUrl}/links/${playerId}`, {
        params: new HttpParams().set('keepHistory', keepHistory),
      }),
    );
  }

  previewInvitation(token: string): Promise<InvitationDto> {
    return firstValueFrom(
      this.http.get<InvitationDto>(`${this.baseUrl}/invitations/${encodeURIComponent(token)}`, {
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  acceptInvitation(token: string, reciprocal: boolean): Promise<void> {
    const body: InvitationAcceptanceDto = { reciprocal };
    return firstValueFrom(
      this.http.post<void>(`${this.baseUrl}/invitations/${encodeURIComponent(token)}`, body, {
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }
}
