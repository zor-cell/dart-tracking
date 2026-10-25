import { DOCUMENT } from '@angular/common';
import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { SocketService } from '../../../core/socket/services/socket.service';
import { DartAnnouncementDto } from '../dto/dart-announcement.dto';
import { announcementPhrases } from '../models/announcement-text';
import { readStored, writeStored } from '../../../core/storage/models/browser-storage';

const MUTED_KEY = 'dart-tracking.announcerMuted';
const ANNOUNCEMENT_LANG = 'de-DE';

/** Spoken nearly silent to prime the synthesiser; must not be empty on WebKit. */
const UNLOCK_PHRASE = 'ok';
const UNLOCK_VOLUME = 0.01;

/** Events that count as a user activation on touch and mouse alike. */
const GESTURE_EVENTS = ['touchend', 'click'] as const;

/** What the self-test says out loud. */
const TEST_PHRASE = 'Ansage funktioniert';

/** Watchdog for an utterance that never reports back, in ms. */
const UTTERANCE_TIMEOUT_BASE = 2000;
const UTTERANCE_TIMEOUT_PER_CHAR = 120;

/** Older WebKit has the audio context under a prefix. */
type WebAudioWindow = Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext };

/** What the synthesiser did with the self-test's utterance. `spoken` says it ran
 * to the end, not that anything was audible. */
export type AnnouncerTestResult = 'spoken' | 'failed' | 'no_answer' | 'muted' | 'unsupported';

/**
 * Speaks the darts the camera books, on the one device the server picked as
 * announcer. Muting is local to this device.
 */
@Injectable({ providedIn: 'root' })
export class AnnouncerService {
  private readonly socket = inject(SocketService);
  private readonly document = inject(DOCUMENT);

  private readonly announcerId = signal<string | null>(null);
  private readonly _muted = signal(readStored(MUTED_KEY) === 'true');

  private readonly pending: string[] = [];
  private audio: AudioContext | null = null;
  private speaking = false;
  private readonly _unlocked = signal(false);
  private watchdog: ReturnType<typeof setTimeout> | null = null;
  private readonly onGesture = () => this.unlock();

  readonly muted = this._muted.asReadonly();
  readonly supported = this.synth() !== null;

  /** Whether an utterance has been heard to start on this device. Until then the
   * browser may be dropping them, which is what the self-test makes visible. */
  readonly unlocked = this._unlocked.asReadonly();
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

    for (const event of GESTURE_EVENTS) {
      this.document.addEventListener(event, this.onGesture, { capture: true });
    }
  }

  claim(): void {
    this.socket.send({ type: 'claim_announcer' });
  }

  toggleMuted(): void {
    const muted = !this._muted();
    this._muted.set(muted);
    writeStored(MUTED_KEY, String(muted));
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

    // WebKit swallows every later utterance once its queue is stuck, and leaves
    // the synthesiser paused after the page was backgrounded.
    synth.cancel();
    synth.resume();

    const utterance = this.utterance(phrase);

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
    if (this._unlocked() || synth === null || this.speaking || synth.pending || synth.speaking) {
      return;
    }
    this.primeAudio();
    const utterance = this.utterance(UNLOCK_PHRASE);
    utterance.volume = UNLOCK_VOLUME;
    synth.resume();
    synth.speak(utterance);
  }

  /**
   * Say one phrase out loud and report what the synthesiser made of it. Speaks
   * from inside the caller's click, the one moment WebKit allows a first
   * utterance.
   */
  test(): Promise<AnnouncerTestResult> {
    const synth = this.synth();
    if (synth === null) {
      return Promise.resolve<AnnouncerTestResult>('unsupported');
    }
    if (this._muted()) {
      return Promise.resolve<AnnouncerTestResult>('muted');
    }

    this.primeAudio();
    this.stop();
    const utterance = this.utterance(TEST_PHRASE);

    return new Promise((resolve) => {
      const settle = (result: AnnouncerTestResult) => {
        if (this.speaking) {
          this.speaking = false;
          this.clearWatchdog();
          resolve(result);
          this.drain();
        }
      };
      utterance.onend = () => settle('spoken');
      utterance.onerror = () => settle('failed');

      // Held like a queued phrase, so an announcement arriving mid-test waits
      // rather than talking over it.
      this.speaking = true;
      this.watchdog = setTimeout(
        () => settle('no_answer'),
        UTTERANCE_TIMEOUT_BASE + TEST_PHRASE.length * UTTERANCE_TIMEOUT_PER_CHAR,
      );
      synth.resume();
      synth.speak(utterance);
    });
  }

  /**
   * Open and resume an audio context, from inside a gesture. iOS keeps speech
   * silent while the page holds no running audio session.
   */
  private primeAudio(): void {
    const view = this.document.defaultView as WebAudioWindow | null;
    const context = view?.AudioContext ?? view?.webkitAudioContext;
    if (context === undefined) {
      return;
    }
    const audio = (this.audio ??= new context());
    void audio.resume().catch(() => {});
  }

  /** An utterance in the announcement voice, and the note that speech works on
   * this device once it starts. */
  private utterance(phrase: string): SpeechSynthesisUtterance {
    const utterance = new SpeechSynthesisUtterance(phrase);
    utterance.lang = ANNOUNCEMENT_LANG;
    const voice = this.germanVoice();
    if (voice !== null) {
      utterance.voice = voice;
    }
    utterance.onstart = () => {
      this._unlocked.set(true);
      for (const event of GESTURE_EVENTS) {
        this.document.removeEventListener(event, this.onGesture, { capture: true });
      }
    };
    return utterance;
  }

  private germanVoice(): SpeechSynthesisVoice | null {
    return (this.synth()?.getVoices() ?? []).find(isGerman) ?? null;
  }

  private synth(): SpeechSynthesis | null {
    return this.document.defaultView?.speechSynthesis ?? null;
  }
}

/** Whether a voice speaks German, whichever way the device writes the tag. */
function isGerman(voice: SpeechSynthesisVoice): boolean {
  return voice.lang.replace('_', '-').toLowerCase().startsWith('de');
}
