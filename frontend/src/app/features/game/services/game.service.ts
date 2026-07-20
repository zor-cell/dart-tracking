import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { GameStateDto } from '../dto/game-state.dto';
import { PlayerDto } from '../dto/player.dto';
import { TurnDto } from '../dto/turn.dto';
import {NotificationService} from "../../../core/services/notification.service";
import {GameConfigDto} from "../dto/game-config.dto";

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

  /** Create a game on the server; the caller navigates once it resolves. */
  createGame(config: GameConfigDto): Observable<GameStateDto> {
    return this.http
      .post<GameStateDto>(this.baseUrl, config)
      .pipe(tap((state) => {
        this.setState(state);
      }));
  }

  registerDart(points: number): void {
    const id = this._state()?.id;
    if (!id) {
      return;
    }
    this.http
      .post<GameStateDto>(`${this.baseUrl}/${id}/darts`, { points })
      .subscribe((state) => this.setState(state));
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

  /** Restore a game after a page refresh from the persisted id. */
  restore(): void {
    const id = localStorage.getItem(STORAGE_KEY);
    if (!id || this._state() !== null) {
      return;
    }
    this.http
      .get<GameStateDto>(`${this.baseUrl}/${id}`, { context: SILENT_ERROR_CONTEXT })
      .subscribe({
        next: (state) => this.setState(state),
        error: () => this.reset(),
      });
  }

  reset(): void {
    this._state.set(null);
    localStorage.removeItem(STORAGE_KEY);
  }

  private setState(state: GameStateDto): void {
    this._state.set(state);
    localStorage.setItem(STORAGE_KEY, state.id);
  }
}
