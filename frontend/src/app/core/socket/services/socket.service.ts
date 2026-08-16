import { Injectable, signal } from '@angular/core';
import { environment } from '../../../../environments/environment';
import { ClientStateDto } from '../dto/client-state.dto';
import { ServerMessage } from '../dto/server-message';
import { ClientFrame, ClientMessage } from '../dto/client-message';
import { DeviceRole } from '../models/device-role';

export type SocketConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

// What this device is called. The server mints it on the first ever connect and
// this is the only thing that has to outlive the tab — everything the server
// knows about the device hangs off it, so nothing else needs storing here.
const CLIENT_ID_KEY = 'dart-tracking.clientId';

/**
 * The connection to the game's room on the server. Every device playing the
 * same game holds one, and it carries everything that is not the session
 * lifecycle: the camera frames of whichever device films the board, and the
 * commands any device issues (see docs/feature/multi-device.md).
 */
@Injectable({ providedIn: 'root' })
export class SocketService {
  readonly connectionStatus = signal<SocketConnectionStatus>('disconnected');
  readonly lastMessage = signal<ServerMessage | null>(null);

  /**
   * What this device does in the game. Owned by the server: `null` until the
   * first `client_state` answers, which is only visible on a cold start —
   * picking a role sets it right away, and the confirmation follows.
   */
  readonly role = signal<DeviceRole | null>(null);

  private socket: WebSocket | null = null;
  private gameId: string | null = null;

  private clientId: string | null = localStorage.getItem(CLIENT_ID_KEY);

  // Commands issued before the socket finished opening, flushed on connect.
  // Only commands are held back: a queued frame would describe a board the game
  // has long moved past, so those are dropped instead (see `sendFrame`).
  private pending: ClientMessage[] = [];

  /**
   * Tell the server what this device does in the game. Requires a socket, so it
   * is issued on the way into a game, right after `connect()` — queued like any
   * other command if the handshake is still in flight.
   *
   * Applied locally straight away so the view has something to render. The
   * server's confirmation is what settles it: the `client_state` of the
   * handshake still carries the previous role and lands first.
   */
  setRole(role: DeviceRole): void {
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
    this.socket = new WebSocket(`${environment.wsApiUrl}/games/${gameId}${this.identity()}`);

    this.socket.addEventListener('open', () => {
      this.connectionStatus.set('connected');
      this.flush();
    });
    this.socket.addEventListener('error', () => this.connectionStatus.set('error'));
    this.socket.addEventListener('close', () => {
      this.connectionStatus.set('disconnected');
      this.socket = null;
    });
    this.socket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data) as ServerMessage;
      if (message.type === 'client_state') {
        this.adopt(message);
      }
      this.lastMessage.set(message);
    });
  }

  disconnect(): void {
    this.socket?.close();
    this.socket = null;
    this.gameId = null;
    this.pending = [];
    this.connectionStatus.set('disconnected');
    this.lastMessage.set(null);
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
  async sendFrame(type: ClientFrame['type'], frame: Blob, debug?: boolean): Promise<void> {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      console.warn('SocketService: Frame verworfen, WebSocket nicht verbunden');
      return;
    }
    const image = await blobToBase64(frame);
    const message: ClientFrame = debug === undefined ? { type, image } : { type, image, debug };
    this.socket.send(JSON.stringify(message));
  }

  /**
   * Name this device to the server — the whole handshake, and deliberately so:
   * everything else it knows about the device hangs off the id, so nothing else
   * belongs in the URL. Absent on a first connect, when there is no name yet.
   */
  private identity(): string {
    return this.clientId ? `?clientId=${encodeURIComponent(this.clientId)}` : '';
  }

  /** Take the server's word for who this device is. */
  private adopt(message: ClientStateDto): void {
    this.clientId = message.clientId;
    localStorage.setItem(CLIENT_ID_KEY, message.clientId);
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
