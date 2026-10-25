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
      const { query, since, until, opponentId, ...rest } = filter;
      for (const [key, value] of Object.entries(rest)) {
        if (value !== null) {
          params = params.set(key, value);
        }
      }
      if (query) {
        params = params.set('q', query);
      }
      if (opponentId) {
        params = params.set('opponent', opponentId);
      }
      if (since) {
        params = params.set('since', since.toISOString());
      }
      if (until) {
        params = params.set('until', until.toISOString());
      }
    }
    return firstValueFrom(
      this.http.get<GamePageDto>(this.baseUrl, { params, context: SILENT_ERROR_CONTEXT }),
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
