import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { environment } from '../../../../environments/environment';
import { PlayerStatisticsDto } from '../dto/player-statistics.dto';

/** The signed-in account's own throwing record. */
@Injectable({ providedIn: 'root' })
export class StatisticsService {
  private readonly http = inject(HttpClient);

  load(): Promise<PlayerStatisticsDto> {
    return firstValueFrom(
      this.http.get<PlayerStatisticsDto>(`${environment.httpApiUrl}/statistics`, {
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }
}
