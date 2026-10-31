import { SERIES_COLORS } from '../../../core/charts/models/series-colors';
import { PlayerStatisticsDto } from '../dto/player-statistics.dto';

/** Another player's figures over the same filters, set beside one's own. */
export interface Comparison {
  readonly name: string;
  readonly statistics: PlayerStatisticsDto;
}

/** Each side's colour in charts and drawings. As text the compared one reads
 * `--compare-text-color`, a shade that keeps its contrast on a light page. */
export const OWN_COLOR = SERIES_COLORS[0];
export const COMPARE_COLOR = SERIES_COLORS[1];
