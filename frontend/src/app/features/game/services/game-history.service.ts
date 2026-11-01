import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { environment } from '../../../../environments/environment';
import { GameDetailDto } from '../dto/game-detail.dto';
import { GamePageDto } from '../dto/game-page.dto';
import { GameFilter } from '../models/game-filter';

/**
 * Games that are over, as opposed to the one being played — `GameService` owns
 * the live session and its socket, this owns the history behind it.
 */
@Injectable({ providedIn: 'root' })
export class GameHistoryService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.httpApiUrl}/games`;

  list(limit: number, offset: number, filter?: GameFilter): Promise<GamePageDto> {
    let params = new HttpParams().set('limit', limit).set('offset', offset);
    if (filter) {
      const lists: Record<string, readonly (string | number)[]> = {
        variant: filter.variants,
        mode: filter.modes,
        checkoutMode: filter.checkoutModes,
        status: filter.statuses,
        opponent: filter.opponentIds,
        players: filter.playerCounts,
      };
      for (const [key, values] of Object.entries(lists)) {
        for (const value of values) {
          params = params.append(key, value);
        }
      }
      if (filter.query) {
        params = params.set('q', filter.query);
      }
      if (filter.since) {
        params = params.set('since', filter.since.toISOString());
      }
      if (filter.until) {
        params = params.set('until', filter.until.toISOString());
      }
      if (filter.minVisit !== null) {
        params = params.set('minVisit', filter.minVisit);
      }
    }
    return firstValueFrom(
      this.http.get<GamePageDto>(this.baseUrl, { params, context: SILENT_ERROR_CONTEXT }),
    );
  }

  /** Takes up a game that is neither won nor discarded; a 404 for any other. */
  resume(gameId: string): Promise<void> {
    return firstValueFrom(
      this.http.post<void>(`${this.baseUrl}/${gameId}/resume`, null, {
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  /** Hides the game from this account's list and statistics, or shows it again. */
  setCounted(gameId: string, counted: boolean): Promise<void> {
    return firstValueFrom(
      this.http.patch<void>(
        `${this.baseUrl}/${gameId}`,
        { status: counted ? 'active' : 'discarded' },
        { context: SILENT_ERROR_CONTEXT },
      ),
    );
  }

  /** Rejects with a 404 unless the account plays in the game or set it up. */
  detail(gameId: string): Promise<GameDetailDto> {
    return firstValueFrom(
      this.http.get<GameDetailDto>(`${this.baseUrl}/${gameId}/detail`, {
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }
}
