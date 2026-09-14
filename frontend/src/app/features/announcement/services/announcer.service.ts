import { DOCUMENT } from '@angular/common';
import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { SocketService } from '../../../core/socket/services/socket.service';
import { DartAnnouncementDto } from '../dto/dart-announcement.dto';
import { announcementPhrases } from '../models/announcement-text';

const MUTED_KEY = 'dart-tracking.announcerMuted';

/**
 * Speaks the darts the camera books, on the one device the server picked as
 * announcer (docs/feature/ansage.md). Muting is local to this device.
 */
@Injectable({ providedIn: 'root' })
export class AnnouncerService {
  private readonly socket = inject(SocketService);
  private readonly document = inject(DOCUMENT);

  private readonly announcerId = signal<string | null>(null);
  private readonly _muted = signal(localStorage.getItem(MUTED_KEY) === 'true');

  readonly muted = this._muted.asReadonly();
  readonly supported = this.synth() !== null;
  readonly isAnnouncer = computed(
    () => this.announcerId() !== null && this.announcerId() === this.socket.clientId(),
  );

  constructor() {
    this.socket
      .on('announcer_state')
      .pipe(takeUntilDestroyed())
      .subscribe((state) => this.announcerId.set(state.clientId));

    this.socket
      .on('dart_announcement')
      .pipe(takeUntilDestroyed())
      .subscribe((announcement) => this.speak(announcement));

    // The room re-sends the announcer on every join, so a stale one must not
    // outlive the connection it came from.
    effect(() => {
      if (this.socket.connectionStatus() !== 'connected') {
        this.announcerId.set(null);
      }
    });

    // Browsers only allow speech after a user gesture; iOS needs the first
    // utterance to start inside one.
    this.document.addEventListener('pointerdown', () => this.unlock(), {
      once: true,
      capture: true,
    });
  }

  claim(): void {
    this.socket.send({ type: 'claim_announcer' });
  }

  toggleMuted(): void {
    const muted = !this._muted();
    this._muted.set(muted);
    localStorage.setItem(MUTED_KEY, String(muted));
    if (muted) {
      this.synth()?.cancel();
    }
  }

  private speak(announcement: DartAnnouncementDto): void {
    const synth = this.synth();
    if (synth === null || this._muted()) {
      return;
    }
    const voice = synth.getVoices().find((v) => v.lang.toLowerCase().startsWith('de')) ?? null;
    for (const phrase of announcementPhrases(announcement)) {
      const utterance = new SpeechSynthesisUtterance(phrase);
      utterance.lang = 'de-DE';
      utterance.voice = voice;
      synth.speak(utterance);
    }
  }

  private unlock(): void {
    const utterance = new SpeechSynthesisUtterance(' ');
    utterance.volume = 0;
    this.synth()?.speak(utterance);
  }

  private synth(): SpeechSynthesis | null {
    return this.document.defaultView?.speechSynthesis ?? null;
  }
}
