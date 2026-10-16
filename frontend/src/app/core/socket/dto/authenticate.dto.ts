/**
 * Client -> server: the signed-in account's access token, which unlocks the
 * admin-only messages (debug frames, `set_evaluation`) on this connection.
 */
export interface AuthenticateDto {
  readonly type: 'authenticate';
  readonly accessToken: string;
}
