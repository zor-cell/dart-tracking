import { DeviceRole } from '../models/device-role';

/**
 * Server -> client: what the server holds about this device, with its `clientId`;
 * sent right after the handshake and after every `set_role`.
 */
export interface ClientStateDto {
  readonly type: 'client_state';
  readonly clientId: string;
  readonly role: DeviceRole;
}
