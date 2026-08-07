import { ConnectionEstablishedMessage } from './connection-established-message';
import { CalibrationResultDto } from '../../../features/calibration/dto/calibration-result.dto';
import { DetectionResultDto } from '../../../features/detection/dto/detection-result.dto';
import { GameStateMessage } from '../../../features/game/dto/game-state-message';

/**
 * Server -> client messages, discriminated by `type`.
 *
 * This union is the only thing that has to know the full set; a message whose
 * payload only means something to one feature is defined by that feature and
 * pulled in here, so the schema sits next to the code that reads it.
 */
export type IncomingMessage =
  ConnectionEstablishedMessage
  | CalibrationResultDto
  | DetectionResultDto
  | GameStateMessage;
