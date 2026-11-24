import { ActivityBucketDto, ActivityDto, ActivityTallyDto, ActivityUnit } from '../dto/activity.dto';
import { GameVariant } from '../../game/models/game-variant';

const UNITS: readonly ActivityUnit[] = ['day', 'week', 'month'];

/** Two players' activity on one axis: the coarser unit of the two, from the earliest bucket
 * to the latest, the empty ones included. */
export function onOneAxis(own: ActivityDto, other: ActivityDto): readonly [ActivityDto, ActivityDto] {
  const unit = UNITS[Math.max(UNITS.indexOf(own.unit), UNITS.indexOf(other.unit))];
  const starts = [...own.buckets, ...other.buckets].map((bucket) => startOf(bucket.start, unit)).sort();
  const axis: string[] = [];
  for (let start = starts[0]; start !== undefined && start <= starts[starts.length - 1]; ) {
    axis.push(start);
    start = next(start, unit);
  }
  return [rebucket(own, unit, axis), rebucket(other, unit, axis)];
}

function rebucket(activity: ActivityDto, unit: ActivityUnit, axis: readonly string[]): ActivityDto {
  const sums = new Map<string, Partial<Record<GameVariant, ActivityTallyDto>>>();
  for (const bucket of activity.buckets) {
    const start = startOf(bucket.start, unit);
    const variants = { ...(sums.get(start) ?? {}) };
    for (const [variant, tally] of Object.entries(bucket.variants) as [GameVariant, ActivityTallyDto][]) {
      variants[variant] = add(variants[variant], tally);
    }
    sums.set(start, variants);
  }
  const buckets: ActivityBucketDto[] = axis.map((start) => ({ start, variants: sums.get(start) ?? {} }));
  return { unit, buckets };
}

function add(sum: ActivityTallyDto | undefined, tally: ActivityTallyDto): ActivityTallyDto {
  return sum
    ? { darts: sum.darts + tally.darts, games: sum.games + tally.games, seconds: sum.seconds + tally.seconds }
    : tally;
}

/** The ISO date the bucket of `unit` holding `day` starts on. */
function startOf(day: string, unit: ActivityUnit): string {
  const date = parse(day);
  if (unit === 'week') {
    date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
  } else if (unit === 'month') {
    date.setUTCDate(1);
  }
  return format(date);
}

function next(start: string, unit: ActivityUnit): string {
  const date = parse(start);
  if (unit === 'month') {
    date.setUTCMonth(date.getUTCMonth() + 1);
  } else {
    date.setUTCDate(date.getUTCDate() + (unit === 'week' ? 7 : 1));
  }
  return format(date);
}

function parse(day: string): Date {
  const [year, month, date] = day.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, date));
}

function format(date: Date): string {
  return date.toISOString().slice(0, 10);
}
