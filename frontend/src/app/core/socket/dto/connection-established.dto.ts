/** Server -> client: sent once right after the WebSocket handshake. */
export interface ConnectionEstablishedDto {
  readonly type: 'connection_established';
}
