import { GameCommand } from '../../../features/game/dto/game-command';

/**
 * Client -> server messages, discriminated by `type`. The counterpart to
 * `SocketMessage`, and aggregated the same way: a message that only means
 * something to one feature is defined by that feature and pulled in here.
 *
 * Camera frames are not part of this union — they carry a base64 payload the
 * caller does not build itself, so they go out through `sendFrame` (see
 * `outgoing-frame-type.ts`).
 */
export type OutgoingMessage = GameCommand;
