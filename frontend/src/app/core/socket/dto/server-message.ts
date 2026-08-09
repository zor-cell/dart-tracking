import { ClientStateDto } from './client-state.dto';
import { CalibrationResultDto } from '../../../features/calibration/dto/calibration-result.dto';
import { DetectionResultDto } from '../../../features/detection/dto/detection-result.dto';
import { GameStateDto } from '../../../features/game/dto/game-state.dto';

/**
 * Everything the server sends, discriminated by `type`.
 *
 * Named after the sender, like `ClientMessage`. The union is the only place that
 * knows the full set; each message is defined by the feature that reads it.
 */
export type ServerMessage =
  | ClientStateDto
  | CalibrationResultDto
  | DetectionResultDto
  | GameStateDto;
