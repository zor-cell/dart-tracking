import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { environment } from '../../../../environments/environment';
import { PlayerStatisticsDto } from '../dto/player-statistics.dto';
import { TrendPointDto } from '../dto/trend-point.dto';
import { StatisticsFilter } from '../models/statistics-filter';

/** The signed-in account's own throwing record. */
@Injectable({ providedIn: 'root' })
export class StatisticsService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.httpApiUrl}/statistics`;

  load(filter: StatisticsFilter): Promise<PlayerStatisticsDto> {
    return firstValueFrom(
      this.http.get<PlayerStatisticsDto>(this.baseUrl, {
        params: this.params(filter),
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  /** The same games one by one, oldest first. */
  trend(filter: StatisticsFilter): Promise<TrendPointDto[]> {
    return firstValueFrom(
      this.http.get<TrendPointDto[]>(`${this.baseUrl}/trend`, {
        params: this.params(filter),
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  private params(filter: StatisticsFilter): HttpParams {
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
    return params;
  }
}
