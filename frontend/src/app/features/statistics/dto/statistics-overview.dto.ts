import { PlayerStatisticsDto } from './player-statistics.dto';
import { TrendPointDto } from './trend-point.dto';

/** The selected games in one tally, and the same games one by one, oldest first. */
export interface StatisticsOverviewDto extends PlayerStatisticsDto {
  readonly trend: readonly TrendPointDto[];
}
