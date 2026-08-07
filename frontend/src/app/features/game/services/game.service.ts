import { HttpClient } from '@angular/common/http';
import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { Observable, firstValueFrom, tap } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { SocketService } from '../../../core/socket/services/socket.service';
import { GameStateDto } from '../dto/game-state.dto';
import { PlayerDto } from '../dto/player.dto';
import { TurnDto } from '../dto/turn.dto';
import {NotificationService} from "../../../core/notification/services/notification.service";
import {GameConfigDto} from "../dto/game-config.dto";
import {SettingsService} from "../../settings/services/settings.service";

const STORAGE_KEY = 'dart-tracking.gameId';

/**
 * Client-side cache of the server-authoritative game state. The server owns the
 * scoring rules (scores originate from the vision pipeline), so this service only
 * mirrors the fetched state — it never derives scores itself. Views read `state`
 * directly; the computed signals below are id/index lookups that would otherwise
 * clutter the templates.
 */
@Injectable({ providedIn: 'root' })
export class GameService {
  private readonly http = inject(HttpClient);
  private readonly socket = inject(SocketService);
  private readonly settings = inject(SettingsService);
  private readonly baseUrl = `${environment.httpApiUrl}/games`;

  private readonly _state = signal<GameStateDto | null>(null);
  readonly state = this._state.asReadonly();

  readonly currentPlayer = computed<PlayerDto | null>(() => {
    const state = this._state();
    return state ? (state.players[state.currentPlayerIndex] ?? null) : null;
  });

  readonly currentTurn = computed<TurnDto | null>(() => this._state()?.turns.at(-1) ?? null);

  readonly winner = computed<PlayerDto | null>(() => {
    const state = this._state();
    if (!state || state.winnerId === null) {
      return null;
    }
    return state.players.find((player) => player.id === state.winnerId) ?? null;
  });

  constructor() {
    //keep game state in sync on websocket updates
    effect(() => {
      const message = this.socket.lastMessage();
      if (message?.type === 'game_state' && this.setState(message.state)) {
        this.maybeAutoAdvance(message.state);
      }
    });
  }

  /** Create a game on the server; the caller navigates once it resolves. */
  createGame(config: GameConfigDto): Observable<GameStateDto> {
    return this.http
      .post<GameStateDto>(this.baseUrl, config)
      .pipe(tap((state) => {
        this.setState(state);
      }));
  }

  /** Book one dart as the field it landed in — the server derives its points and
   * the called-out label from that. */
  registerDart(value: number, multiplier: number): void {
    const id = this._state()?.id;
    if (!id) {
      return;
    }
    this.http
      .post<GameStateDto>(`${this.baseUrl}/${id}/darts`, { value, multiplier })
      .subscribe((state) => {
        if (this.setState(state)) {
          this.maybeAutoAdvance(state);
        }
      });
  }

  /**
   * Advance to the next player once a visit is complete — but only when the
   * confirm button is turned off. With it on (the default) the player ends the
   * visit by tapping confirm instead, in both entry modes. The server no longer
   * auto-advances, so this client decision applies uniformly to manual darts
   * (HTTP response) and camera darts (`game_state` push).
   */
  private maybeAutoAdvance(state: GameStateDto): void {
    if (
      state.dartsRemaining === 0 &&
      state.winnerId === null &&
      !this.settings.confirmThrowEnabled()
    ) {
      this.nextPlayer();
    }
  }

  /** Step back one action — a dart, or the switch to the current player. */
  undo(): void {
    const id = this._state()?.id;
    if (!id) {
      return;
    }
    this.http
      .post<GameStateDto>(`${this.baseUrl}/${id}/undo`, {})
      .subscribe((state) => this.setState(state));
  }

  nextPlayer(): void {
    const id = this._state()?.id;
    if (!id) {
      return;
    }
    this.http
      .post<GameStateDto>(`${this.baseUrl}/${id}/next-player`, {})
      .subscribe((state) => this.setState(state));
  }

  /** The active game's id, even before its state has been (re)fetched — read
   * from the live state, falling back to the id persisted across refreshes. */
  peekGameId(): string | null {
    return this._state()?.id ?? localStorage.getItem(STORAGE_KEY);
  }

  /**
   * Ensure the game state is loaded, refetching from the persisted id after a
   * page refresh. Resolves to whether a game is active — false when there is no
   * persisted id or the server no longer knows it (a stale id is cleared).
   * Idempotent: a no-op once the state is already in hand.
   */
  async ensureRestored(): Promise<boolean> {
    if (this._state() !== null) {
      return true;
    }
    const id = localStorage.getItem(STORAGE_KEY);
    if (!id) {
      return false;
    }
    try {
      const state = await firstValueFrom(
        this.http.get<GameStateDto>(`${this.baseUrl}/${id}`, { context: SILENT_ERROR_CONTEXT }),
      );
      this.setState(state);
      return true;
    } catch {
      this.reset();
      return false;
    }
  }

  reset(): void {
    this._state.set(null);
    localStorage.removeItem(STORAGE_KEY);
  }

  /**
   * Adopt a snapshot unless it is one the cache has already moved past.
   *
   * The same state reaches this service twice — as the answer to this device's
   * own call and as the broadcast to the game's room — and the two can arrive in
   * either order, so a slow response must not overwrite a newer push. The
   * revision only orders snapshots of the *same* game; a different id is always
   * a new game and always wins.
   *
   * Returns whether the state was taken, so a caller can skip follow-up work on
   * a snapshot it has already acted upon.
   */
  private setState(state: GameStateDto): boolean {
    const current = this._state();
    if (current?.id === state.id && state.revision <= current.revision) {
      return false;
    }
    this._state.set(state);
    localStorage.setItem(STORAGE_KEY, state.id);
    return true;
  }
}
