import { Injectable, signal } from '@angular/core';
import { environment } from '../../../../environments/environment';
import { DartSocketMessage } from '../dto/dart-socket-message';
import { SocketConnectionStatus } from '../models/types';

@Injectable({ providedIn: 'root' })
export class DartSocketService {
  readonly connectionStatus = signal<SocketConnectionStatus>('disconnected');
  readonly lastMessage = signal<DartSocketMessage | null>(null);

  private socket: WebSocket | null = null;

  connect(): void {
    if (this.socket) {
      return;
    }

    this.connectionStatus.set('connecting');
    this.socket = new WebSocket(environment.backendWsUrl);

    this.socket.addEventListener('open', () => this.connectionStatus.set('connected'));
    this.socket.addEventListener('error', () => this.connectionStatus.set('error'));
    this.socket.addEventListener('close', () => {
      this.connectionStatus.set('disconnected');
      this.socket = null;
    });
    this.socket.addEventListener('message', (event) => {
      this.lastMessage.set(JSON.parse(event.data) as DartSocketMessage);
    });
  }

  disconnect(): void {
    this.socket?.close();
    this.socket = null;
    this.connectionStatus.set('disconnected');
  }

  sendFrame(frame: Blob): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(frame);
    } else {
      console.warn('DartSocketService: Frame verworfen, WebSocket nicht verbunden');
    }
  }
}
