import { CalibrationResultMessage } from './calibration-result-message';
import { ConnectionEstablishedMessage } from './connection-established-message';
import { GameStateMessage } from './game-state-message';
import { ThrowReceivedMessage } from './throw-received-message';

/** Server -> client messages, discriminated by `type` (see docs/roadmap.md §4). */
export type DartSocketMessage =
  | ConnectionEstablishedMessage
  | CalibrationResultMessage
  | ThrowReceivedMessage
  | GameStateMessage;
