import { UserDto } from './user.dto';

/** The refresh token is not in here — it stays in an httpOnly cookie. */
export interface SessionDto {
  readonly accessToken: string;
  readonly expiresIn: number;
  readonly user: UserDto;
}
