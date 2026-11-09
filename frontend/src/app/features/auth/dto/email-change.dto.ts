import { IdentityConfirmationDto } from './identity-confirmation.dto';

export interface EmailChangeDto extends IdentityConfirmationDto {
  readonly newEmail: string;
}
