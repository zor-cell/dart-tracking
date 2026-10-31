import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { environment } from '../../../../environments/environment';
import { StatisticsOverviewDto } from '../dto/statistics-overview.dto';
import { StatisticsFilter } from '../models/statistics-filter';

/** The signed-in account's own throwing record, or that of a player from its address book
 * in the games the account can see. */
@Injectable({ providedIn: 'root' })
export class StatisticsService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.httpApiUrl}/statistics`;

  load(filter: StatisticsFilter, player: string | null = null): Promise<StatisticsOverviewDto> {
    return firstValueFrom(
      this.http.get<StatisticsOverviewDto>(this.baseUrl, {
        params: this.params(filter, player),
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  private params(filter: StatisticsFilter, player: string | null): HttpParams {
    const { opponentId, since, until, lastGames, ...rest } = filter;
    let params = new HttpParams();
    for (const [key, value] of Object.entries(rest)) {
      if (value !== null) {
        params = params.set(key, value);
      }
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
    if (lastGames !== null) {
      params = params.set('last', lastGames);
    }
    if (player) {
      params = params.set('player', player);
    }
    return params;
  }
}
