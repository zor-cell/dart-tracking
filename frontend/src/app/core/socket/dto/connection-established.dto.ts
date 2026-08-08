import { DeviceRole } from '../models/device-role';

/**
 * Server -> client: sent once right after the WebSocket handshake.
 *
 * It tells the device who it is: `clientId` is its name from here on, and the
 * role is what the server has on record for it — which is how a device that
 * just reloaded finds out what it was.
 */
export interface ConnectionEstablishedDto {
  readonly type: 'connection_established';
  readonly clientId: string;
  readonly role: DeviceRole;
}
