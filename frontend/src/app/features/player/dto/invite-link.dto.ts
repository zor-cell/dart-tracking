/** The secret an invitation link carries, and when it stops working. */
export interface InviteLinkDto {
  readonly token: string;
  readonly expiresAt: string;
}
