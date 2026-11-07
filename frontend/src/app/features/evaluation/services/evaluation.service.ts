import { HttpClient, HttpParams } from '@angular/common/http';
import { DOCUMENT } from '@angular/common';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { environment } from '../../../../environments/environment';
import { AccuracyReportDto, GameReportDto } from '../dto/accuracy.dto';
import { EvaluationFilter } from '../models/evaluation-filter';

/** The file name the report falls back to when the server names none. */
const REPORT_FILE = 'accuracy.md';

/** How well the tracker scored, over the games that left an event log. */
@Injectable({ providedIn: 'root' })
export class EvaluationService {
  private readonly http = inject(HttpClient);
  private readonly document = inject(DOCUMENT);
  private readonly baseUrl = `${environment.httpApiUrl}/evaluation`;

  loadAccuracy(filter: EvaluationFilter): Promise<AccuracyReportDto> {
    return firstValueFrom(
      this.http.get<AccuracyReportDto>(`${this.baseUrl}/accuracy`, {
        params: filterParams(filter),
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  /** One game's figures, whatever the page's filters. */
  loadGame(gameId: string): Promise<GameReportDto> {
    return firstValueFrom(
      this.http.get<GameReportDto>(`${this.baseUrl}/games/${encodeURIComponent(gameId)}`, {
        context: SILENT_ERROR_CONTEXT,
      }),
    );
  }

  /** The same selection as a Markdown report, saved as a file. */
  async downloadReport(filter: EvaluationFilter): Promise<void> {
    const response = await firstValueFrom(
      this.http.get(`${this.baseUrl}/report`, {
        params: filterParams(filter),
        observe: 'response',
        responseType: 'blob',
      }),
    );
    const disposition = response.headers.get('Content-Disposition') ?? '';
    const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? REPORT_FILE;
    const url = URL.createObjectURL(response.body ?? new Blob());
    const link = this.document.createElement('a');
    link.href = url;
    link.download = name;
    link.click();
    URL.revokeObjectURL(url);
  }

  /** The tracker versions there are logged games of, newest first. */
  loadVersions(): Promise<number[]> {
    return firstValueFrom(
      this.http.get<number[]>(`${this.baseUrl}/versions`, { context: SILENT_ERROR_CONTEXT }),
    );
  }
}

/** The filter as query parameters; an open bound is left out. */
export function filterParams(filter: EvaluationFilter): HttpParams {
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
  return params;
}
