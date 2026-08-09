import { DeviceRole } from '../models/device-role';

/**
 * Client -> server: what this device does in the game from now on.
 *
 * A command rather than a handshake parameter. The role lives on the server's
 * client record and outlives the socket, so connecting only has to say which
 * device this is; the one moment the role changes — the way into a game — is
 * stated explicitly instead of riding along on every connect.
 */
export interface SetRoleDto {
  readonly type: 'set_role';
  readonly role: DeviceRole;
}
