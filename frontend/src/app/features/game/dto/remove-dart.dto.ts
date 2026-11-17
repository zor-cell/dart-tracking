import { DartCorrectionDto } from './dart-correction.dto';

/** Client -> server: take one dart out of a visit, by its position in it; a closed
 * visit keeps it as a miss. */
export interface RemoveDartDto extends DartCorrectionDto {
  readonly type: 'remove_dart';
  readonly index: number;
}
