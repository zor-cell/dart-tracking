export interface TurnDto {
  readonly playerId: number;
  readonly darts: readonly number[];
  readonly busted: boolean;
}
