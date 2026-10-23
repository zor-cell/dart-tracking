/** German text for a failed `getUserMedia`, keyed on the DOMException's name. */
export function cameraErrorMessage(error: unknown): string {
  const name = error instanceof Error ? error.name : '';
  switch (name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return 'Kamerazugriff verweigert. Bitte in den Browser-Einstellungen erlauben.';
    case 'NotFoundError':
    case 'OverconstrainedError':
      return 'Keine passende Kamera gefunden.';
    case 'NotReadableError':
    case 'AbortError':
      return 'Die Kamera wird gerade von einer anderen App verwendet.';
    default:
      return 'Die Kamera konnte nicht gestartet werden.';
  }
}
