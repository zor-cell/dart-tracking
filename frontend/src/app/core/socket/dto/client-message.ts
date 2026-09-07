import { SetRoleDto } from './set-role.dto';
import { CalibrationFrameDto } from '../../../features/calibration/dto/calibration-frame.dto';
import { RequestCalibrationDto } from '../../../features/calibration/dto/request-calibration.dto';
import { DetectionFrameDto } from '../../../features/detection/dto/detection-frame.dto';
import { NextPlayerDto } from '../../../features/game/dto/next-player.dto';
import { RegisterDartDto } from '../../../features/game/dto/register-dart.dto';
import { SetEvaluationDto } from '../../../features/game/dto/set-evaluation.dto';
import { UndoDto } from '../../../features/game/dto/undo.dto';

/**
 * Everything this client sends, discriminated by `type`.
 *
 * Named after the sender, so the term means the same here as in the backend's
 * `client_message.py`. The union is the only place that knows the full set;
 * each message is defined by the feature it belongs to.
 */
export type ClientMessage =
  | CalibrationFrameDto
  | RequestCalibrationDto
  | DetectionFrameDto
  | SetRoleDto
  | RegisterDartDto
  | SetEvaluationDto
  | UndoDto
  | NextPlayerDto;

/** The camera frames within that set: sent via `sendFrame`, and dropped rather
 * than queued when the socket is not open. */
export type ClientFrame = CalibrationFrameDto | DetectionFrameDto;
