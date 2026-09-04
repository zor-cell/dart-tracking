import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { GameSummaryDto } from '../dto/game-summary.dto';

/**
 * Games that are over, as opposed to the one being played — `GameService` owns
 * the live session and its socket, this owns the history behind it.
 */
@Injectable({ providedIn: 'root' })
export class GameHistoryService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.httpApiUrl}/games`;

  list(limit: number, offset: number): Promise<GameSummaryDto[]> {
    return firstValueFrom(
      this.http.get<GameSummaryDto[]>(this.baseUrl, {
        params: new HttpParams().set('limit', limit).set('offset', offset),
      }),
    );
  }

  /** Take a game out of the statistics, or let it count again. */
  setCounted(gameId: string, counted: boolean): Promise<void> {
    return firstValueFrom(
      this.http.patch<void>(`${this.baseUrl}/${gameId}`, {
        status: counted ? 'active' : 'discarded',
      }),
    );
  }
}
