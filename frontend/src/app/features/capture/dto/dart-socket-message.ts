import { GameStateDto } from '../../game/dto/game-state.dto';

/** Server -> client messages, discriminated by `type` (see docs/roadmap.md §4). */
export type DartSocketMessage =
  | { type: 'connection_established' }
  | { type: 'calibration_result'; success: boolean; homography: number[][] | null }
  | { type: 'throw_received'; bytesReceived: number }
  | { type: 'game_state'; state: GameStateDto };

/** Client -> server frame kinds; the payload is always a base64-encoded JPEG. */
export type OutgoingFrameType = 'calibration_frame' | 'throw_frame';
