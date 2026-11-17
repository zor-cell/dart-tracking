import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { environment } from '../../../../environments/environment';
import { CricketStatisticsDto } from '../dto/cricket-statistics.dto';
import { KillStatisticsDto } from '../dto/kill-statistics.dto';
import { OverallStatisticsDto } from '../dto/overall-statistics.dto';
import { ScoringStatisticsDto } from '../dto/scoring-statistics.dto';
import { StatisticsOverviewDto } from '../dto/statistics-overview.dto';
import { TargetStatisticsDto } from '../dto/target-statistics.dto';
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

  /** The darts thrown at named fields in the games the filter selects. */
  targets(filter: StatisticsFilter, player: string | null = null): Promise<TargetStatisticsDto> {
    return firstValueFrom(
      this.http.get<TargetStatisticsDto>(`${this.baseUrl}/targets`, {
        params: this.params(filter, player),
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  /** The points of the trainings without a target that the filter selects. */
  scoring(filter: StatisticsFilter): Promise<ScoringStatisticsDto> {
    return firstValueFrom(
      this.http.get<ScoringStatisticsDto>(`${this.baseUrl}/scoring`, {
        params: this.params(filter, null),
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  /** Every finished game of any kind the filter selects, added up. */
  overall(filter: StatisticsFilter): Promise<OverallStatisticsDto> {
    return firstValueFrom(
      this.http.get<OverallStatisticsDto>(`${this.baseUrl}/all`, {
        params: this.params(filter, null),
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  /** The kills in the Elimination and Killer games the filter selects. */
  kills(filter: StatisticsFilter): Promise<KillStatisticsDto> {
    return firstValueFrom(
      this.http.get<KillStatisticsDto>(`${this.baseUrl}/kills`, {
        params: this.params(filter, null),
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  /** Marks, distances, visits and the hit picture of the Cricket games the filter selects. */
  cricket(filter: StatisticsFilter): Promise<CricketStatisticsDto> {
    return firstValueFrom(
      this.http.get<CricketStatisticsDto>(`${this.baseUrl}/cricket`, {
        params: this.params(filter, null),
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  private params(filter: StatisticsFilter, player: string | null): HttpParams {
    const lists: Record<string, readonly (string | number)[]> = {
      variant: filter.variants,
      mode: filter.modes,
      checkoutMode: filter.checkoutModes,
      killerZone: filter.killerZones,
      scoring: filter.cricketScorings,
      clockZone: filter.clockZones,
      trainingGoal: filter.trainingGoals,
      trainingRing: filter.trainingRings,
      opponent: filter.opponentIds,
      players: filter.playerCounts,
    };
    let params = new HttpParams();
    for (const [key, values] of Object.entries(lists)) {
      for (const value of values) {
        params = params.append(key, value);
      }
    }
    if (filter.since) {
      params = params.set('since', filter.since.toISOString());
    }
    if (filter.until) {
      params = params.set('until', filter.until.toISOString());
    }
    if (filter.lastGames !== null) {
      params = params.set('last', filter.lastGames);
    }
    if (player) {
      params = params.set('player', player);
    }
    return params;
  }
}
