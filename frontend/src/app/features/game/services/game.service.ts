import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Observable, firstValueFrom, tap } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { SocketService } from '../../../core/socket/services/socket.service';
import { GameStateDto } from '../dto/game-state.dto';
import { PlayerDto } from '../dto/player.dto';
import { TurnDto } from '../dto/turn.dto';
import { DARTS_PER_TURN } from '../models/visit';
import {GameConfigDto} from "../dto/game-config.dto";
import {SettingsService} from "../../settings/services/settings.service";
import { ACTIVE_GAME_KEY } from "./active-game";


/**
 * Client-side cache of the server-authoritative game state. The server owns the
 * scoring rules (scores originate from the vision pipeline), so this service only
 * mirrors the fetched state — it never derives scores itself. Views read `state`
 * directly; the computed signals below are id/index lookups that would otherwise
 * clutter the templates.
 *
 * It also owns the socket's lifetime, because the connection follows the game
 * and not the camera: a device that only keeps score joins the same room and
 * must see every change.
 */
@Injectable({ providedIn: 'root' })
export class GameService {
  private readonly http = inject(HttpClient);
  private readonly socket = inject(SocketService);
  private readonly settings = inject(SettingsService);
  private readonly baseUrl = `${environment.httpApiUrl}/games`;

  private readonly _state = signal<GameStateDto | null>(null);
  readonly state = this._state.asReadonly();

  private readonly _winConfirmed = signal(false);

  readonly currentTurn = computed<TurnDto | null>(() => this._state()?.turns.at(-1) ?? null);

  readonly winner = computed<PlayerDto | null>(() => {
    const state = this._state();
    if (!state || state.winnerId === null) {
      return null;
    }
    return state.players.find((player) => player.id === state.winnerId) ?? null;
  });

  /** Shadow darts of the open visit: located after a win or bust, booked once a correction reopens it. */
  readonly shadowDarts = computed(() => this._state()?.shadowDarts ?? []);

  /** Whether the camera keeps sending throws: while the visit has physical room
   * left and no win is settled — past a win or bust they arrive as shadow darts. */
  readonly tracksThrows = computed(
    () =>
      this._state() !== null &&
      this.settledWinner() === null &&
      (this.currentTurn()?.darts.length ?? 0) + this.shadowDarts().length < DARTS_PER_TURN,
  );

  /** Whether the keypad may append: into any visit with room left, busted or
   * won but unconfirmed, as the server's `Game.add_dart` allows. */
  readonly acceptsManualDarts = computed(
    () =>
      this.settledWinner() === null && (this.currentTurn()?.darts.length ?? 0) < DARTS_PER_TURN,
  );

  /** A win that still waits for the confirm tap, the same gate every other visit
   * passes through. Never pending while confirming is off. */
  readonly winPending = computed(
    () => this.winner() !== null && this.settings.confirmThrowEnabled() && !this._winConfirmed(),
  );

  /** The winner once the win is settled — what the view shows the game as over
   * by. `winner` alone is only the score reading it rests on. */
  readonly settledWinner = computed<PlayerDto | null>(() =>
    this.winPending() ? null : this.winner(),
  );

  constructor() {
    // The only route by which a change reaches this cache: commands are sent
    // over the socket and answered with a push, never with a response body.
    this.socket
      .on('game_state')
      .pipe(takeUntilDestroyed())
      .subscribe((state) => {
        if (this.setState(state)) {
          this.maybeAutoAdvance(state);
        }
      });

    // Every device in the room follows a rematch; its role stays with the device.
    this.socket
      .on('rematch_started')
      .pipe(takeUntilDestroyed())
      .subscribe(({ gameId }) => {
        if (gameId !== this.peekGameId()) {
          void this.join(gameId);
        }
      });
  }

  /** Create a game on the server; the caller navigates once it resolves. */
  createGame(config: GameConfigDto): Observable<GameStateDto> {
    return this.http
      .post<GameStateDto>(this.baseUrl, config)
      .pipe(tap((state) => {
        this.setState(state);
        this.connect();
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

  /** Take one dart out of the open visit; the darts after it move up. */
  removeDart(index: number): void {
    this.socket.send({ type: 'remove_dart', index });
  }

  /** Book a different field for one dart of the open visit, in its place. */
  replaceDart(index: number, value: number, multiplier: number): void {
    this.socket.send({ type: 'replace_dart', index, value, multiplier });
  }

  /** Move one dart of the open visit to another place in it. */
  moveDart(index: number, toIndex: number): void {
    this.socket.send({ type: 'move_dart', index, toIndex });
  }

  /** Switch to the next player */
  nextPlayer(): void {
    this.socket.send({ type: 'next_player' });
  }

  /** Take the winning dart as thrown. Local to this device: the server has
   * nothing left to apply, and confirming is a per-device setting. */
  confirmWin(): void {
    this._winConfirmed.set(true);
  }

  /** Mark the running game as a tracking test run, or stop. Game-wide: it is
   * the game that is measured, not the device saying so. */
  setEvaluation(enabled: boolean): void {
    this.socket.send({ type: 'set_evaluation', enabled });
  }

  /** The active game's id, even before its state has been (re)fetched — read
   * from the live state, falling back to the id persisted across refreshes. */
  peekGameId(): string | null {
    return this._state()?.id ?? localStorage.getItem(ACTIVE_GAME_KEY);
  }

  /**
   * Adopt a game's state without joining its room yet. Resolves to false when
   * the server does not know the id — a shared link whose game has since ended,
   * or a stale one from before a restart.
   *
   * Separate from `connect()` for the join screen, which shows the game before
   * asking what this device will be — and only enters the room once that is
   * answered, so a device that turns back was never in it.
   */
  async load(gameId: string): Promise<boolean> {
    const state = await this.fetch(gameId);
    if (state === null) {
      return false;
    }
    this.setState(state);
    return true;
  }

  /** Read a game without adopting it — the setup screen copies a finished one's
   * seats from it. Resolves to null when the server does not know the id. */
  async fetch(gameId: string): Promise<GameStateDto | null> {
    try {
      return await firstValueFrom(
        this.http.get<GameStateDto>(`${this.baseUrl}/${gameId}`, {
          context: SILENT_ERROR_CONTEXT,
        }),
      );
    } catch {
      return null;
    }
  }

  /** Join the loaded game's room, so every device's changes arrive here. */
  connect(): void {
    const gameId = this.peekGameId();
    if (gameId) {
      this.socket.connect(gameId);
    }
  }

  /**
   * Make a game the active one on this device: adopt its state and join its
   * room. This is the same operation whether the id comes from a shared link or
   * from `localStorage` after a refresh; only what to do on failure differs.
   */
  async join(gameId: string): Promise<boolean> {
    if (!(await this.load(gameId))) {
      return false;
    }
    this.connect();
    return true;
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
    const id = localStorage.getItem(ACTIVE_GAME_KEY);
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
    localStorage.removeItem(ACTIVE_GAME_KEY);
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
    // An undo past the winning dart puts the game back in play, so the next win
    // is asked about again.
    if (state.winnerId === null) {
      this._winConfirmed.set(false);
    }
    localStorage.setItem(ACTIVE_GAME_KEY, state.id);
    return true;
  }
}
