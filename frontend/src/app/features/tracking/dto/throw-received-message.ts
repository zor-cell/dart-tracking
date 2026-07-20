/**
 * Server -> client: acknowledgement of a throw frame.
 *
 * Stub for now — dart localization/scoring from the frame is future work
 * (see roadmap.md §4, `dart_detected`); this just confirms receipt.
 */
export interface ThrowReceivedMessage {
  readonly type: 'throw_received';
  readonly bytesReceived: number;
}
