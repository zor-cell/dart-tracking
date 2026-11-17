import { DartDto } from './dart.dto';

export interface TurnDto {
  readonly playerId: number;
  readonly darts: readonly DartDto[];
  readonly busted: boolean;
}
