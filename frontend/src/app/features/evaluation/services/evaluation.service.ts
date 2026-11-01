import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { environment } from '../../../../environments/environment';
import { AccuracyReportDto } from '../dto/accuracy.dto';
import { EvaluationFilter } from '../models/evaluation-filter';

/** How well the tracker scored, over the games that left an event log. */
@Injectable({ providedIn: 'root' })
export class EvaluationService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.httpApiUrl}/evaluation`;

  loadAccuracy(filter: EvaluationFilter): Promise<AccuracyReportDto> {
    let params = new HttpParams();
    for (const mode of filter.modes) {
      params = params.append('mode', mode);
    }
    const values: Record<string, number | boolean | null> = {
      versionFrom: filter.versionFrom,
      versionTo: filter.versionTo,
      testRun: filter.testRun,
      tiltFrom: filter.tiltFrom,
      tiltTo: filter.tiltTo,
    };
    for (const [key, value] of Object.entries(values)) {
      if (value !== null) {
        params = params.set(key, value);
      }
    }
    if (filter.since) {
      params = params.set('since', filter.since.toISOString());
    }
    if (filter.until) {
      params = params.set('until', filter.until.toISOString());
    }
    return firstValueFrom(
      this.http.get<AccuracyReportDto>(`${this.baseUrl}/accuracy`, {
        params,
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  /** The tracker versions there are logged games of, newest first. */
  loadVersions(): Promise<number[]> {
    return firstValueFrom(
      this.http.get<number[]>(`${this.baseUrl}/versions`, { context: SILENT_ERROR_CONTEXT }),
    );
  }
}
