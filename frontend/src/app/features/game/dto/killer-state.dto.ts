import { KillerOptionsDto } from './killer-options.dto';

export interface KillerPlayerDto {
  readonly number: number;
  readonly lives: number;
  readonly killer: boolean;
  /** Lives this player took from others. */
  readonly kills: number;
}

export interface KillerStateDto extends KillerOptionsDto {
  /** One per player, in seat order. */
  readonly players: readonly KillerPlayerDto[];
}
