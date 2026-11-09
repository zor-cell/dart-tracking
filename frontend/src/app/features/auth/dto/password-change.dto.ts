import { IdentityConfirmationDto } from './identity-confirmation.dto';

export interface PasswordChangeDto extends IdentityConfirmationDto {
  readonly newPassword: string;
}
