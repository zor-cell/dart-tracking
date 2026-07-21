import { Injectable, signal } from '@angular/core';
import { environment } from '../../../../environments/environment';
import { SocketMessage } from '../dto/socket-message';
import { OutgoingFrameType } from '../dto/outgoing-frame-type';

export type SocketConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

@Injectable({ providedIn: 'root' })
export class SocketService {
  readonly connectionStatus = signal<SocketConnectionStatus>('disconnected');
  readonly lastMessage = signal<SocketMessage | null>(null);

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
      this.lastMessage.set(JSON.parse(event.data) as SocketMessage);
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
