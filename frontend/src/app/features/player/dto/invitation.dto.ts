import { ReciprocalLink } from '../models/reciprocal-link';

/** What accepting an invitation would link. */
export interface InvitationDto {
  readonly inviterName: string;
  readonly playerName: string;
  readonly gameCount: number;
  readonly reciprocal: ReciprocalLink;
}
