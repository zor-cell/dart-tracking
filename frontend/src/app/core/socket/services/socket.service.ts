import { Injectable, signal } from '@angular/core';
import { Observable, Subject, filter } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ClientStateDto } from '../dto/client-state.dto';
import { ServerMessage } from '../dto/server-message';
import { ClientFrame, ClientMessage } from '../dto/client-message';
import { DeviceRole } from '../models/device-role';
import { ThrowTriggerDto } from '../../../features/detection/dto/throw-trigger.dto';

export type SocketConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

// What this device is called. The server mints it on the first ever connect and
// this is the only thing that has to outlive the tab — everything the server
// knows about the device hangs off it, so nothing else needs storing here.
const CLIENT_ID_KEY = 'dart-tracking.clientId';

/**
 * The connection to the game's room on the server. Every device playing the
 * same game holds one, and it carries everything that is not the session
 * lifecycle: the camera frames of whichever device films the board, and the
 * commands any device issues (see docs/feature/done/multi-device.md).
 */
@Injectable({ providedIn: 'root' })
export class SocketService {
  readonly connectionStatus = signal<SocketConnectionStatus>('disconnected');

  /**
   * What this device does in the game. Owned by the server: `null` until the
   * first `client_state` answers, which is only visible on a cold start —
   * picking a role sets it right away, and the confirmation follows.
   */
  readonly role = signal<DeviceRole | null>(null);

  private socket: WebSocket | null = null;
  private gameId: string | null = null;

  private readonly messages = new Subject<ServerMessage>();

  private readonly _clientId = signal<string | null>(localStorage.getItem(CLIENT_ID_KEY));
  readonly clientId = this._clientId.asReadonly();

  // Commands issued before the socket finished opening, flushed on connect.
  // Only commands are held back: a queued frame would describe a board the game
  // has long moved past, so those are dropped instead (see `sendFrame`).
  private pending: ClientMessage[] = [];

  // A role asked for but not yet confirmed. The handshake answers with the role
  // the device had *before* the command, which must not overwrite the new one.
  private requestedRole: DeviceRole | null = null;

  /**
   * Tell the server what this device does in the game. Requires a socket, so it
   * is issued on the way into a game, right after `connect()` — queued like any
   * other command if the handshake is still in flight.
   *
   * Applied locally straight away so the view has something to render, and held
   * against the handshake's answer until the server confirms it (see `adopt`).
   */
  setRole(role: DeviceRole): void {
    this.requestedRole = role;
    this.role.set(role);
    this.send({ type: 'set_role', role });
  }

  connect(gameId: string): void {
    if (this.socket && this.gameId === gameId) {
      return;
    }
    // A different game means a different room; the old connection has nothing
    // left to carry.
    this.disconnect();

    this.gameId = gameId;
    this.connectionStatus.set('connecting');
    const socket = new WebSocket(`${environment.wsApiUrl}/games/${gameId}${this.identity()}`);
    this.socket = socket;

    // Events of a socket already replaced by a newer connect must not touch the current one.
    const current = () => this.socket === socket;

    socket.addEventListener('open', () => {
      if (!current()) {
        return;
      }
      this.connectionStatus.set('connected');
      this.flush();
    });
    socket.addEventListener('error', () => {
      if (current()) {
        this.connectionStatus.set('error');
      }
    });
    socket.addEventListener('close', () => {
      if (current()) {
        this.connectionStatus.set('disconnected');
        this.socket = null;
      }
    });
    socket.addEventListener('message', (event) => {
      if (!current()) {
        return;
      }
      const message = JSON.parse(event.data) as ServerMessage;
      if (message.type === 'client_state') {
        this.adopt(message);
      }
      this.messages.next(message);
    });
  }

  disconnect(): void {
    this.socket?.close();
    this.socket = null;
    this.gameId = null;
    this.pending = [];
    this.requestedRole = null;
    this.connectionStatus.set('disconnected');
  }

  /**
   * The stream of one kind of server message, in arrival order. Deliberately not
   * a signal: two messages arriving back to back would collapse into one value,
   * and the first would never be observed (docs/feature/done/multi-device.md §6a).
   */
  on<T extends ServerMessage['type']>(type: T): Observable<Extract<ServerMessage, { type: T }>> {
    return this.messages.pipe(
      filter((message): message is Extract<ServerMessage, { type: T }> => message.type === type),
    );
  }

  /**
   * Ask the server to change the game. There is no reply to await — the new
   * state arrives as the `game_state` push that goes to the whole room.
   *
   * A command sent while the socket is still opening is queued rather than
   * dropped: the game view is on screen as soon as the state is loaded, so a
   * quick tap can easily beat the handshake, and a silently swallowed dart is
   * indistinguishable from a dead button.
   */
  send(message: ClientMessage): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    } else if (this.socket?.readyState === WebSocket.CONNECTING) {
      this.pending.push(message);
    } else {
      console.warn('SocketService: Nachricht verworfen, WebSocket nicht verbunden', message);
    }
  }

  /**
   * Send a camera frame. Unlike `send`, an unsendable frame is dropped rather
   * than queued — by the time the socket opened it would describe a board the
   * game has already moved past.
   */
  async sendFrame(
    type: ClientFrame['type'],
    frame: Blob,
    debug?: boolean,
    trigger?: ThrowTriggerDto,
  ): Promise<void> {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      console.warn('SocketService: Frame verworfen, WebSocket nicht verbunden');
      return;
    }
    const image = await blobToBase64(frame);
    const message: ClientFrame =
      type === 'detection_frame' ? { type, image, debug, trigger } : { type, image, debug };
    this.socket.send(JSON.stringify(message));
  }

  /**
   * Name this device to the server — the whole handshake, and deliberately so:
   * everything else it knows about the device hangs off the id, so nothing else
   * belongs in the URL. Absent on a first connect, when there is no name yet.
   */
  private identity(): string {
    const clientId = this._clientId();
    return clientId ? `?clientId=${encodeURIComponent(clientId)}` : '';
  }

  /** Take the server's word for who this device is, except while a role change
   * is in flight: its confirmation is the message that clears the request, and
   * anything before it still carries the old role. */
  private adopt(message: ClientStateDto): void {
    this._clientId.set(message.clientId);
    localStorage.setItem(CLIENT_ID_KEY, message.clientId);

    if (this.requestedRole !== null && message.role !== this.requestedRole) {
      return;
    }
    this.requestedRole = null;
    this.role.set(message.role);
  }

  private flush(): void {
    const queued = this.pending;
    this.pending = [];
    queued.forEach((message) => this.socket?.send(JSON.stringify(message)));
  }
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      resolve(result.slice(result.indexOf(',') + 1));
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}
