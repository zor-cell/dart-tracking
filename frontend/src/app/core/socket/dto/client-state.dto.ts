import { DeviceRole } from '../models/device-role';

/**
 * Server -> client: what the server holds about this device.
 *
 * Sent right after the handshake, where it also carries the `clientId` this
 * device is named by from here on, and again after every `set_role`. One
 * message for the whole record — the counterpart of `game_state`, which does
 * the same for the state the room shares.
 *
 * It is how a device that just reloaded finds out what it was: the record
 * outlives the socket, so nothing about the role has to be stored here.
 */
export interface ClientStateDto {
  readonly type: 'client_state';
  readonly clientId: string;
  readonly role: DeviceRole;
}
