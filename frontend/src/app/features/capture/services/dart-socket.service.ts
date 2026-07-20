import { Injectable, signal } from '@angular/core';
import { environment } from '../../../../environments/environment';
import { DartSocketMessage, OutgoingFrameType } from '../dto/dart-socket-message';
import { SocketConnectionStatus } from '../models/types';

@Injectable({ providedIn: 'root' })
export class DartSocketService {
  readonly connectionStatus = signal<SocketConnectionStatus>('disconnected');
  readonly lastMessage = signal<DartSocketMessage | null>(null);

  private socket: WebSocket | null = null;

  connect(gameId: string): void {
    if (this.socket) {
      return;
    }

    this.connectionStatus.set('connecting');
    this.socket = new WebSocket(`${environment.wsApiUrl}/games/${gameId}`);

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

  async sendFrame(type: OutgoingFrameType, frame: Blob): Promise<void> {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      console.warn('DartSocketService: Frame verworfen, WebSocket nicht verbunden');
      return;
    }
    const image = await blobToBase64(frame);
    this.socket.send(JSON.stringify({ type, image }));
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
