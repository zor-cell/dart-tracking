import { DOCUMENT } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { SocketService } from '../../../core/socket/services/socket.service';
import { readStored, writeStored } from '../../../core/storage/models/browser-storage';
import { SpeechTestDto } from '../dto/speech-test.dto';

const MUTED_KEY = 'dart-tracking.announcerMuted';

/** Events that count as a user activation on touch and mouse alike. */
const GESTURE_EVENTS = ['touchend', 'click'] as const;

/** Decoded clips kept for reuse, since the fixed calls repeat all game long. */
const CLIP_CACHE_SIZE = 64;

/** How long the self-test waits for its clip to play through, in ms. */
const TEST_TIMEOUT = 8000;

/** Older WebKit has the audio context under a prefix. */
type WebAudioWindow = Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext };

/** What became of the self-test's clip. `spoken` says it played to the end, not
 * that anything was audible. */
export type AnnouncerTestResult = 'spoken' | 'failed' | 'no_answer' | 'muted' | 'unsupported';

/**
 * Plays the clips the server voices for booked darts and the next player, on the
 * one device the server picked as announcer. Muting is local to this device.
 */
@Injectable({ providedIn: 'root' })
export class AnnouncerService {
  private readonly socket = inject(SocketService);
  private readonly http = inject(HttpClient);
  private readonly document = inject(DOCUMENT);

  private readonly announcerId = signal<string | null>(null);
  private readonly _muted = signal(readStored(MUTED_KEY) === 'true');
  private readonly _unlocked = signal(false);

  private audio: AudioContext | null = null;
  private readonly clips = new Map<string, Promise<AudioBuffer>>();
  /** Bumped by every interruption, so the clips of an older announcement stop. */
  private generation = 0;
  private queue: Promise<unknown> = Promise.resolve();
  private current: AudioBufferSourceNode | null = null;

  readonly muted = this._muted.asReadonly();
  readonly supported = this.contextType() !== null;

  /** Whether the browser lets this page play sound; until a tap it may not. */
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
      .subscribe((announcement) => this.announce(announcement.clips, true));

    this.socket
      .on('turn_announcement')
      .pipe(takeUntilDestroyed())
      .subscribe((announcement) => this.announce(announcement.clips));

    this.socket
      .on('calibration_announcement')
      .pipe(takeUntilDestroyed())
      .subscribe((announcement) => this.announce(announcement.clips));

    // The room re-sends the announcer on every join, so a stale one must not
    // outlive the connection it came from.
    effect(() => {
      if (this.socket.connectionStatus() !== 'connected') {
        this.announcerId.set(null);
      }
    });

    for (const event of GESTURE_EVENTS) {
      this.document.addEventListener(event, () => this.resume(), { capture: true });
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

  private announce(urls: readonly string[], interrupt = false): void {
    void this.play(urls, interrupt).catch(() => undefined);
  }

  /** Play one clip after the other, behind the announcements before. With
   * `interrupt`, cuts those off, so quick manual entries do not queue up.
   * Resolves whether every clip played to the end. */
  private play(urls: readonly string[], interrupt = false): Promise<boolean> {
    const audio = this.context();
    if (audio === null || this._muted() || urls.length === 0) {
      return Promise.resolve(false);
    }
    if (interrupt) {
      this.stop();
    }
    const generation = this.generation;
    const buffers = urls.map((url) => this.clip(audio, url));
    const played = this.queue.then(() => this.playInTurn(audio, buffers, generation));
    this.queue = played.catch(() => undefined);
    return played;
  }

  private async playInTurn(
    audio: AudioContext,
    buffers: readonly Promise<AudioBuffer>[],
    generation: number,
  ): Promise<boolean> {
    for (const buffer of buffers) {
      const decoded = await buffer;
      // A suspended context never ends a clip; the call is dropped rather than held.
      if (generation !== this.generation || audio.state !== 'running') {
        return false;
      }
      await this.playClip(audio, decoded);
    }
    return generation === this.generation;
  }

  private playClip(audio: AudioContext, buffer: AudioBuffer): Promise<void> {
    return new Promise((resolve) => {
      const source = audio.createBufferSource();
      source.buffer = buffer;
      source.connect(audio.destination);
      source.onended = () => {
        if (this.current === source) {
          this.current = null;
        }
        resolve();
      };
      this.current = source;
      source.start();
    });
  }

  private stop(): void {
    this.generation++;
    const current = this.current;
    this.current = null;
    current?.stop();
  }

  /** A clip fetched and decoded once, then reused. */
  private clip(audio: AudioContext, url: string): Promise<AudioBuffer> {
    const cached = this.clips.get(url);
    if (cached !== undefined) {
      return cached;
    }
    const decoded = firstValueFrom(
      this.http.get(url, { responseType: 'arraybuffer', context: SILENT_ERROR_CONTEXT }),
    ).then((data) => audio.decodeAudioData(data));
    decoded.catch(() => this.clips.delete(url));
    this.clips.set(url, decoded);
    if (this.clips.size > CLIP_CACHE_SIZE) {
      this.clips.delete(this.clips.keys().next().value!);
    }
    return decoded;
  }

  /**
   * Play the server's test phrase and report what became of it. Resumes the
   * audio before anything is awaited, the one moment WebKit allows it.
   */
  async test(): Promise<AnnouncerTestResult> {
    const audio = this.context();
    if (audio === null) {
      return 'unsupported';
    }
    if (this._muted()) {
      return 'muted';
    }
    const resumed = audio.resume().catch(() => undefined);
    this.stop();

    let clips: readonly string[];
    try {
      const test = this.http.get<SpeechTestDto>(`${environment.httpApiUrl}/announcer/test`, {
        context: SILENT_ERROR_CONTEXT,
      });
      clips = (await firstValueFrom(test)).clips;
    } catch {
      return 'failed';
    }
    await resumed;
    if (clips.length === 0) {
      return 'failed';
    }
    if (audio.state !== 'running') {
      return 'no_answer';
    }

    let timer: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise<AnnouncerTestResult>((resolve) => {
      timer = setTimeout(() => resolve('no_answer'), TEST_TIMEOUT);
    });
    const played = this.play(clips).then(
      (done): AnnouncerTestResult => (done ? 'spoken' : 'failed'),
      (): AnnouncerTestResult => 'failed',
    );
    const result = await Promise.race([played, timeout]);
    clearTimeout(timer);
    return result;
  }

  /** Browsers only allow sound after a user gesture, so every tap resumes the audio. */
  private resume(): void {
    const audio = this.context();
    if (audio !== null && audio.state !== 'running') {
      void audio.resume().catch(() => undefined);
    }
  }

  private context(): AudioContext | null {
    if (this.audio === null) {
      const context = this.contextType();
      if (context === null) {
        return null;
      }
      this.audio = new context();
      const audio = this.audio;
      const note = () => this._unlocked.set(audio.state === 'running');
      audio.addEventListener('statechange', note);
      note();
    }
    return this.audio;
  }

  private contextType(): typeof AudioContext | null {
    const view = this.document.defaultView as WebAudioWindow | null;
    return view?.AudioContext ?? view?.webkitAudioContext ?? null;
  }
}
