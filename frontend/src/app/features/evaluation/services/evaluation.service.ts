import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AccuracyReportDto } from '../dto/accuracy.dto';

/** How well the tracker scored, over every game that left an event log. */
@Injectable({ providedIn: 'root' })
export class EvaluationService {
  private readonly http = inject(HttpClient);

  loadAccuracy(): Promise<AccuracyReportDto> {
    return firstValueFrom(
      this.http.get<AccuracyReportDto>(`${environment.httpApiUrl}/evaluation/accuracy`),
    );
  }
}
