import { HttpClient } from '@angular/common/http';
import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { Observable, firstValueFrom, tap } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { SocketService } from '../../../core/socket/services/socket.service';
import { GameStateDto } from '../dto/game-state.dto';
import { PlayerDto } from '../dto/player.dto';
import { TurnDto } from '../dto/turn.dto';
import {GameConfigDto} from "../dto/game-config.dto";
import {SettingsService} from "../../settings/services/settings.service";

const STORAGE_KEY = 'dart-tracking.gameId';

/**
 * Client-side cache of the server-authoritative game state. The server owns the
 * scoring rules (scores originate from the vision pipeline), so this service only
 * mirrors the fetched state — it never derives scores itself. Views read `state`
 * directly; the computed signals below are id/index lookups that would otherwise
 * clutter the templates.
 *
 * It also owns the socket's lifetime, because the connection follows the game
 * and not the camera: a device that only keeps score joins the same room and
 * must see every change (see docs/feature/multi-device.md).
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
    // The only route by which a change reaches this cache: commands are sent
    // over the socket and answered with a push, never with a response body.
    effect(() => {
      const message = this.socket.lastMessage();
      if (message?.type === 'game_state' && this.setState(message)) {
        this.maybeAutoAdvance(message);
      }
    });
  }

  /** Create a game on the server; the caller navigates once it resolves. */
  createGame(config: GameConfigDto): Observable<GameStateDto> {
    return this.http
      .post<GameStateDto>(this.baseUrl, config)
      .pipe(tap((state) => {
        this.setState(state);
        this.socket.connect(state.id);
      }));
  }

  /** Book one dart as the field it landed in — the server derives its points and
   * the called-out label from that. */
  registerDart(value: number, multiplier: number): void {
    this.socket.send({ type: 'register_dart', value, multiplier });
  }

  /** Step back one action — a dart, or the switch to the current player. */
  undo(): void {
    this.socket.send({ type: 'undo' });
  }

  /** Switch to the next player */
  nextPlayer(): void {
    this.socket.send({ type: 'next_player' });
  }

  /** The active game's id, even before its state has been (re)fetched — read
   * from the live state, falling back to the id persisted across refreshes. */
  peekGameId(): string | null {
    return this._state()?.id ?? localStorage.getItem(STORAGE_KEY);
  }

  /**
   * Make a game the active one on this device: fetch its state and join its
   * room. Resolves to false when the server does not know the id — a shared
   * link whose game has since ended, or a stale one from before a restart.
   *
   * This is the same operation whether the id comes from a shared link or from
   * `localStorage` after a refresh; only what to do on failure differs.
   */
  async join(gameId: string): Promise<boolean> {
    try {
      const state = await firstValueFrom(
        this.http.get<GameStateDto>(`${this.baseUrl}/${gameId}`, {
          context: SILENT_ERROR_CONTEXT,
        }),
      );
      this.setState(state);
      this.socket.connect(state.id);
      return true;
    } catch {
      return false;
    }
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
    if (await this.join(id)) {
      return true;
    }
    this.reset();
    return false;
  }

  /** Leave the game entirely: the cached state goes, and with it the room. */
  reset(): void {
    this._state.set(null);
    localStorage.removeItem(STORAGE_KEY);
    this.socket.disconnect();
  }

  /**
   * Advance to the next player once a visit is complete — but only when the
   * confirm button is turned off.
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

  /**
   * Adopt a snapshot unless it is one the cache has already moved past.
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
