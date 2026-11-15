import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { readStored, writeStored } from '../../../core/storage/models/browser-storage';
import { environment } from '../../../../environments/environment';
import { ClaimableGamesQueryDto } from '../dto/claimable-games-query.dto';
import { GameClaimTokenDto } from '../dto/game-claim-token.dto';
import { GameClaimDto } from '../dto/game-claim.dto';
import { GameSummaryDto } from '../dto/game-summary.dto';

const CLAIMS_KEY = 'dart-tracking.gameClaims';
/** Anonymous games this device keeps a token for, newest first. */
const MAX_CLAIMS = 20;

/** The anonymous games this device set up, and handing them to the signed-in account. */
@Injectable({ providedIn: 'root' })
export class GameClaimService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.httpApiUrl}/games`;

  remember(gameId: string, token: string): void {
    this.store([{ gameId, token }, ...this.stored().filter((claim) => claim.gameId !== gameId)]);
  }

  forget(gameId: string): void {
    this.store(this.stored().filter((claim) => claim.gameId !== gameId));
  }

  /** The kept games the account can still take over; the others are forgotten. */
  async claimable(): Promise<GameSummaryDto[]> {
    const claims = this.stored();
    if (claims.length === 0) {
      return [];
    }
    const body: ClaimableGamesQueryDto = { claims };
    const games = await firstValueFrom(
      this.http.post<GameSummaryDto[]>(`${this.baseUrl}/claimable`, body, {
        context: SILENT_ERROR_CONTEXT,
      }),
    );
    const open = new Set(games.map((game) => game.id));
    this.store(this.stored().filter((claim) => open.has(claim.gameId)));
    return games;
  }

  /** Seat the account on `seat`, or on none; a game that cannot be claimed any more is forgotten. */
  async claim(gameId: string, seat: number | null): Promise<void> {
    const token = this.stored().find((claim) => claim.gameId === gameId)?.token ?? '';
    const body: GameClaimDto = { token, seat };
    try {
      await firstValueFrom(
        this.http.post<void>(`${this.baseUrl}/${gameId}/claim`, body, {
          context: SILENT_ERROR_CONTEXT,
        }),
      );
    } catch (failure) {
      if (failure instanceof HttpErrorResponse && failure.status === 404) {
        this.forget(gameId);
      }
      throw failure;
    }
    this.forget(gameId);
  }

  private stored(): GameClaimTokenDto[] {
    try {
      const claims = JSON.parse(readStored(CLAIMS_KEY) ?? '[]') as unknown;
      return Array.isArray(claims) ? (claims as GameClaimTokenDto[]) : [];
    } catch {
      return [];
    }
  }

  private store(claims: readonly GameClaimTokenDto[]): void {
    writeStored(CLAIMS_KEY, claims.length > 0 ? JSON.stringify(claims.slice(0, MAX_CLAIMS)) : null);
  }
}
