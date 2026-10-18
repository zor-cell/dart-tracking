import { DOCUMENT } from '@angular/common';
import { Injectable, inject } from '@angular/core';

/**
 * Keeps the screen on while held. The browser drops the lock whenever the page
 * is hidden, so it is requested again each time the page becomes visible.
 */
@Injectable({ providedIn: 'root' })
export class ScreenWakeLockService {
  private readonly document = inject(DOCUMENT);

  private held = false;
  private sentinel: WakeLockSentinel | null = null;

  private readonly onVisibilityChange = (): void => {
    if (this.document.visibilityState === 'visible') {
      void this.request();
    }
  };

  hold(): void {
    if (this.held) {
      return;
    }
    this.held = true;
    this.document.addEventListener('visibilitychange', this.onVisibilityChange);
    void this.request();
  }

  release(): void {
    this.held = false;
    this.document.removeEventListener('visibilitychange', this.onVisibilityChange);
    void this.sentinel?.release();
    this.sentinel = null;
  }

  private async request(): Promise<void> {
    const wakeLock = this.document.defaultView?.navigator.wakeLock;
    if (!wakeLock || (this.sentinel && !this.sentinel.released)) {
      return;
    }
    try {
      const sentinel = await wakeLock.request('screen');
      // Released while the request was pending.
      if (!this.held) {
        void sentinel.release();
        return;
      }
      this.sentinel = sentinel;
    } catch {
      // Refused, e.g. without HTTPS or in power-saving mode; the screen may dim.
    }
  }
}
