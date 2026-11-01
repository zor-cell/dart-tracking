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
    for (const version of filter.versions) {
      params = params.append('version', version);
    }
    for (const mode of filter.modes) {
      params = params.append('mode', mode);
    }
    if (filter.testRun !== null) {
      params = params.set('testRun', filter.testRun);
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
