/** One counted game's figures; the checkout stays a pair so a running rate can pool it. */
export interface TrendPointDto {
  readonly gameId: string;
  readonly playedAt: string;
  readonly darts: number;
  readonly average: number;
  readonly firstNineAverage: number;
  readonly checkoutHits: number;
  readonly checkoutAttempts: number;
}
