import type { HttpResponse } from '@angular/common/http';

/** Saves a downloaded file under the name the server gives, else `fallbackName`. */
export function saveDownload(document: Document, response: HttpResponse<Blob>, fallbackName: string): void {
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(response.body ?? new Blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
