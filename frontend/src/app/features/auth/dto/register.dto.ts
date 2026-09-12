import { ProfileDto } from './profile.dto';

export interface RegisterDto extends ProfileDto {
  readonly email: string;
  readonly password: string;
}
