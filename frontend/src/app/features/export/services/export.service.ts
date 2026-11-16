import { HttpClient } from '@angular/common/http';
import { DOCUMENT } from '@angular/common';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { saveDownload } from '../../../core/storage/models/save-download';
import { environment } from '../../../../environments/environment';

/** The file name the export falls back to when the server names none. */
const EXPORT_FILE = 'dart-tracking.zip';

/** The signed-in account's data as one zip download. */
@Injectable({ providedIn: 'root' })
export class ExportService {
  private readonly http = inject(HttpClient);
  private readonly document = inject(DOCUMENT);
  private readonly baseUrl = `${environment.httpApiUrl}/export`;

  /** Saves the export; `frames` adds the camera frames of the account's test runs. */
  async download(frames: boolean): Promise<void> {
    const response = await firstValueFrom(
      this.http.get(this.baseUrl, {
        params: { frames },
        observe: 'response',
        responseType: 'blob',
        context: SILENT_ERROR_CONTEXT,
      }),
    );
    saveDownload(this.document, response, EXPORT_FILE);
  }
}
