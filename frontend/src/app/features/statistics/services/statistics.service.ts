import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { environment } from '../../../../environments/environment';
import { PlayerStatisticsDto } from '../dto/player-statistics.dto';
import { StatisticsFilter } from '../models/statistics-filter';

/** The signed-in account's own throwing record. */
@Injectable({ providedIn: 'root' })
export class StatisticsService {
  private readonly http = inject(HttpClient);

  load(filter: StatisticsFilter): Promise<PlayerStatisticsDto> {
    const { opponentId, since, until, ...rest } = filter;
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
    return firstValueFrom(
      this.http.get<PlayerStatisticsDto>(`${environment.httpApiUrl}/statistics`, {
        params,
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }
}
