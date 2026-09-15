import { ClientStateDto } from './client-state.dto';
import { AnnouncerStateDto } from '../../../features/announcement/dto/announcer-state.dto';
import { DartAnnouncementDto } from '../../../features/announcement/dto/dart-announcement.dto';
import { CalibrationRequestedDto } from '../../../features/calibration/dto/calibration-requested.dto';
import { CalibrationResultDto } from '../../../features/calibration/dto/calibration-result.dto';
import { CalibrationStatusDto } from '../../../features/calibration/dto/calibration-status.dto';
import { DetectionResultDto } from '../../../features/detection/dto/detection-result.dto';
import { GameStateDto } from '../../../features/game/dto/game-state.dto';
import { RematchStartedDto } from '../../../features/game/dto/rematch-started.dto';

/**
 * Everything the server sends, discriminated by `type`.
 *
 * Named after the sender, like `ClientMessage`. The union is the only place that
 * knows the full set; each message is defined by the feature that reads it.
 */
export type ServerMessage =
  | ClientStateDto
  | CalibrationRequestedDto
  | CalibrationResultDto
  | CalibrationStatusDto
  | DetectionResultDto
  | GameStateDto
  | AnnouncerStateDto
  | DartAnnouncementDto
  | RematchStartedDto;
