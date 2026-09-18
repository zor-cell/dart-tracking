import { DOCUMENT } from '@angular/common';
import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { SocketService } from '../../../core/socket/services/socket.service';
import { DartAnnouncementDto } from '../dto/dart-announcement.dto';
import { announcementPhrases } from '../models/announcement-text';

const MUTED_KEY = 'dart-tracking.announcerMuted';
const ANNOUNCEMENT_LANG = 'de-DE';

/** Spoken at volume 0 to prime the synthesiser; must not be empty on WebKit. */
const UNLOCK_PHRASE = 'ok';

/** Watchdog for an utterance that never reports back, in ms. */
const UTTERANCE_TIMEOUT_BASE = 2000;
const UTTERANCE_TIMEOUT_PER_CHAR = 120;

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

  private readonly pending: string[] = [];
  private speaking = false;
  private unlocked = false;
  private watchdog: ReturnType<typeof setTimeout> | null = null;
  private readonly onGesture = () => this.unlock();

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

    this.document.addEventListener('pointerdown', this.onGesture, { capture: true });
  }

  claim(): void {
    this.socket.send({ type: 'claim_announcer' });
  }

  toggleMuted(): void {
    const muted = !this._muted();
    this._muted.set(muted);
    localStorage.setItem(MUTED_KEY, String(muted));
    if (muted) {
      this.stop();
    }
  }

  private speak(announcement: DartAnnouncementDto): void {
    if (this.synth() === null || this._muted()) {
      return;
    }
    this.pending.push(...announcementPhrases(announcement));
    this.drain();
  }

  /** Speaks one phrase at a time; WebKit drops all but the head of its queue. */
  private drain(): void {
    const synth = this.synth();
    if (synth === null || this.speaking) {
      return;
    }
    const phrase = this.pending.shift();
    if (phrase === undefined) {
      return;
    }

    // WebKit leaves the synthesiser paused after the page was backgrounded.
    synth.resume();

    const utterance = new SpeechSynthesisUtterance(phrase);
    utterance.lang = ANNOUNCEMENT_LANG;
    const voice = this.germanVoice();
    if (voice !== null) {
      utterance.voice = voice;
    }

    const finish = () => {
      if (!this.speaking) {
        return;
      }
      this.speaking = false;
      this.clearWatchdog();
      this.drain();
    };
    utterance.onend = finish;
    utterance.onerror = finish;

    this.speaking = true;
    this.watchdog = setTimeout(
      finish,
      UTTERANCE_TIMEOUT_BASE + phrase.length * UTTERANCE_TIMEOUT_PER_CHAR,
    );
    synth.speak(utterance);
  }

  private stop(): void {
    this.pending.length = 0;
    this.speaking = false;
    this.clearWatchdog();
    this.synth()?.cancel();
  }

  private clearWatchdog(): void {
    if (this.watchdog !== null) {
      clearTimeout(this.watchdog);
      this.watchdog = null;
    }
  }

  /**
   * Browsers only allow speech after a user gesture. WebKit grants it when an
   * utterance actually starts inside one, so every tap retries until it does.
   */
  private unlock(): void {
    const synth = this.synth();
    if (this.unlocked || synth === null || this.speaking) {
      return;
    }
    const utterance = new SpeechSynthesisUtterance(UNLOCK_PHRASE);
    utterance.volume = 0;
    utterance.lang = ANNOUNCEMENT_LANG;
    utterance.onstart = () => {
      this.unlocked = true;
      this.document.removeEventListener('pointerdown', this.onGesture, { capture: true });
    };
    synth.resume();
    synth.speak(utterance);
  }

  private germanVoice(): SpeechSynthesisVoice | null {
    const voices = this.synth()?.getVoices() ?? [];
    return voices.find((v) => v.lang.replace('_', '-').toLowerCase().startsWith('de')) ?? null;
  }

  private synth(): SpeechSynthesis | null {
    return this.document.defaultView?.speechSynthesis ?? null;
  }
}
