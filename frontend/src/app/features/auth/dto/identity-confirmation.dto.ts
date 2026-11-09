/** Proof for a sensitive change: the current password, or a fresh Google sign-in. */
export interface IdentityConfirmationDto {
  readonly currentPassword?: string;
  readonly googleCredential?: string;
}
