export type UserRole = 'user' | 'admin';

export interface UserDto {
  readonly id: string;
  readonly email: string;
  readonly username: string;
  readonly displayName: string;
  readonly createdAt: string;
  readonly role: UserRole;
  readonly emailVerified: boolean;
}
