import { IdentityConfirmationDto } from '../dto/identity-confirmation.dto';

/** The Google token once one was given, else the typed password. */
export function identityProof(
  password: string,
  googleCredential: string | null,
): IdentityConfirmationDto {
  return googleCredential !== null ? { googleCredential } : { currentPassword: password };
}
