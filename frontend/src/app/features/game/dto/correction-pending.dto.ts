import { MoveDartDto } from './move-dart.dto';
import { RemoveDartDto } from './remove-dart.dto';
import { ReplaceDartDto } from './replace-dart.dto';

/** Server -> the sending device: a correction in a closed visit that waits for it to
 * accept what it changes; sent back confirmed, it is booked. */
export interface CorrectionPendingDto {
  readonly type: 'correction_pending';
  readonly command: ReplaceDartDto | RemoveDartDto | MoveDartDto;
  /** The visit, from 0, that now wins the game, and who wins it; null without a win. */
  readonly wonAt: number | null;
  readonly winnerId: number | null;
  /** Visits thrown after the winning one, which the win drops. */
  readonly dropped: number;
  /** Players now out or placed before visits they threw. */
  readonly outIds: readonly number[];
}
