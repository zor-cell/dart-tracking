import { ConnectionEstablishedMessage } from './connection-established-message';
import { CalibrationResultMessage } from '../../../features/calibration/dto/calibration-result-message';
import { ThrowReceivedMessage } from '../../../features/detection/dto/throw-received-message';
import { GameStateMessage } from '../../../features/game/dto/game-state-message';

/**
 * Server -> client messages, discriminated by `type` (see docs/roadmap.md §4).
 *
 * This union is the only thing that has to know the full set; a message whose
 * payload only means something to one feature is defined by that feature and
 * pulled in here, so the schema sits next to the code that reads it.
 */
export type SocketMessage =
  | ConnectionEstablishedMessage
  | CalibrationResultMessage
  | ThrowReceivedMessage
  | GameStateMessage;
