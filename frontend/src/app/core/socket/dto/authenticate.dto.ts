/**
 * Client -> server: the signed-in account's access token, which unlocks the
 * account's messages (debug frames, the owner's `set_evaluation`) on this connection.
 */
export interface AuthenticateDto {
  readonly type: 'authenticate';
  readonly accessToken: string;
}
