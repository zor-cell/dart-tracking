import { DeviceRole } from '../models/device-role';

/** Client -> server: what this device does in the game from now on. */
export interface SetRoleDto {
  readonly type: 'set_role';
  readonly role: DeviceRole;
}
