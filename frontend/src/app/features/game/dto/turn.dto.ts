import { DartDto } from './dart.dto';

export interface TurnDto {
  readonly darts: readonly DartDto[];
  readonly busted: boolean;
}
