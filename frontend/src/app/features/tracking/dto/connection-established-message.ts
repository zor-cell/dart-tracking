/** Server -> client: sent once right after the WebSocket handshake. */
export interface ConnectionEstablishedMessage {
  readonly type: 'connection_established';
}
