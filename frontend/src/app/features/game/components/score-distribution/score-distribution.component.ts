import { DOCUMENT, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import type { ChartData, ChartOptions, Plugin, ScriptableContext } from 'chart.js';
import { UIChart } from 'primeng/chart';
import { chartTheme, countLabelsPlugin } from '../../../../core/charts/models/chart-plugins';
import { SERIES_COLORS } from '../../../../core/charts/models/series-colors';
import { PlayerDto } from '../../dto/player.dto';
import { VisitDto } from '../../dto/visit.dto';

/** Highest score of a single visit. */
const MAX_VISIT = 180;

/** Room beyond 0 and 180 so dots there are not cut in half, in points. */
const EDGE = 6;

/** Vertical offsets within a player's row, so close scores sit side by side. */
const LANES = [0, -0.14, 0.14, -0.28, 0.28];

/** Scores closer than this share a lane only if nothing else is free. */
const LANE_DISTANCE = 7;

/** Half the height of the average mark, in row units. */
const AVERAGE_HALF_HEIGHT = 0.36;

/** Height of one player's row, in pixels. */
const ROW_HEIGHT = 56;

/** Dot radius for a single visit, and for one that stands for several equal ones. */
const DOT_RADIUS = 5;
const MERGED_DOT_RADIUS = 8;

/** Visits with the same score share one dot; `count` is how many, `rounds` which. */
interface StripPoint {
  readonly x: number;
  readonly y: number;
  readonly count: number;
  readonly rounds: readonly number[];
}

/** Every visit of every player as a dot on 0–180, one row per player, the average marked. */
@Component({
  selector: 'app-score-distribution',
  imports: [UIChart],
  providers: [DecimalPipe],
  templateUrl: './score-distribution.component.html',
  styleUrl: './score-distribution.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ScoreDistributionComponent {
  readonly visits = input.required<readonly VisitDto[]>();
  readonly players = input.required<readonly PlayerDto[]>();

  private readonly theme = chartTheme(inject(DOCUMENT));
  private readonly decimal = inject(DecimalPipe);

  protected readonly plugins: Plugin<'scatter'>[] = [countLabelsPlugin];

  protected readonly height = computed(() => `${this.players().length * ROW_HEIGHT + 48}px`);

  private readonly averages = computed(() =>
    this.players().map((player) => {
      const points = this.visits()
        .filter((visit) => visit.playerId === player.id)
        .map((visit) => visit.points);
      return points.length === 0 ? null : points.reduce((sum, p) => sum + p, 0) / points.length;
    }),
  );

  protected readonly data = computed<ChartData<'scatter', StripPoint[]>>(() => {
    const seats = this.players().length;
    const visits = this.visits();
    const dots = this.players().map((player, row) => {
      const color = SERIES_COLORS[player.id % SERIES_COLORS.length];
      const own = visits
        .map((visit, index) => ({ visit, round: Math.floor(index / seats) + 1 }))
        .filter(({ visit }) => visit.playerId === player.id);
      return {
        type: 'scatter' as const,
        label: player.name,
        data: spread(merge(own.map(({ visit, round }) => ({ x: visit.points, round }))), row),
        backgroundColor: `${color}cc`,
        borderColor: this.theme.surface,
        borderWidth: 1.5,
        pointRadius: (context: ScriptableContext<'scatter'>) => radius(context),
        pointHoverRadius: (context: ScriptableContext<'scatter'>) => radius(context) + 1,
        order: 0,
      };
    });
    const averages = this.averages().flatMap((average, row) =>
      average === null
        ? []
        : [
            {
              type: 'line' as const,
              label: `Durchschnitt ${this.players()[row].name}`,
              data: [
                { x: average, y: row - AVERAGE_HALF_HEIGHT, count: 1, rounds: [] },
                { x: average, y: row + AVERAGE_HALF_HEIGHT, count: 1, rounds: [] },
              ],
              borderColor: this.theme.text,
              borderWidth: 2,
              pointRadius: 0,
              pointHoverRadius: 0,
              // Drawn beneath the dots, which carry the detail.
              order: 1,
            },
          ],
    );
    return { datasets: [...dots, ...averages] as ChartData<'scatter', StripPoint[]>['datasets'] };
  });

  protected readonly options = computed<ChartOptions<'scatter'>>(() => {
    const { text, muted, grid, surface, border, font } = this.theme;
    const names = this.players().map((player) => player.name);
    const averages = this.averages();
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      font: { family: font },
      layout: { padding: { right: 8 } },
      scales: {
        x: {
          min: -EDGE,
          max: MAX_VISIT + EDGE,
          grid: { color: grid },
          border: { display: false },
          afterBuildTicks: (scale) => {
            scale.ticks = Array.from({ length: MAX_VISIT / 20 + 1 }, (_, i) => ({ value: i * 20 }));
          },
          ticks: { color: muted, font: { family: font, size: 10 } },
          title: { display: true, text: 'Punkte pro Aufnahme', color: muted, font: { family: font, size: 10 } },
        },
        y: {
          reverse: true,
          min: -0.6,
          max: names.length - 0.4,
          grid: { display: false },
          border: { display: false },
          afterBuildTicks: (scale) => {
            scale.ticks = names.map((_, row) => ({ value: row }));
          },
          ticks: {
            color: text,
            font: { family: font, size: 11 },
            callback: (value) => names[Number(value)] ?? '',
          },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: surface,
          borderColor: border,
          borderWidth: 1,
          titleColor: muted,
          bodyColor: text,
          titleFont: { family: font, size: 11, weight: 'normal' },
          bodyFont: { family: font, size: 12 },
          padding: 8,
          displayColors: false,
          // The dot datasets come first, one per player; the average marks follow.
          filter: (item) => item.datasetIndex < names.length,
          callbacks: {
            title: (items) => {
              const row = Math.round(items[0]?.parsed.y ?? 0);
              const average = averages[row];
              const shown = average === null ? '' : ` · Ø ${this.decimal.transform(average, '1.1-1')}`;
              return `${names[row] ?? ''}${shown}`;
            },
            label: (item) => {
              const point = item.raw as StripPoint;
              const rounds = point.rounds.join(', ');
              return point.count === 1 ? `Runde ${rounds}: ${point.x}` : `Runden ${rounds}: je ${point.x}`;
            },
          },
        },
      },
    };
  });

  protected readonly ariaLabel = computed(() => {
    const rows = this.players().map((player, row) => {
      const points = this.visits()
        .filter((visit) => visit.playerId === player.id)
        .map((visit) => visit.points)
        .join(', ');
      const average = this.averages()[row];
      const shown = average === null ? '' : `, Durchschnitt ${this.decimal.transform(average, '1.1-1')}`;
      return `${player.name}: ${points}${shown}`;
    });
    return `Punkte jeder Aufnahme pro Spieler. ${rows.join('. ')}`;
  });
}

/** One point per distinct score, carrying the rounds it was thrown in. */
function merge(visits: readonly { x: number; round: number }[]): { x: number; rounds: number[] }[] {
  const byScore = new Map<number, number[]>();
  for (const visit of visits) {
    byScore.set(visit.x, [...(byScore.get(visit.x) ?? []), visit.round]);
  }
  return [...byScore].map(([x, rounds]) => ({ x, rounds }));
}

/** Places a row's dots, moving each to the first lane its neighbour does not crowd. */
function spread(points: readonly { x: number; rounds: number[] }[], row: number): StripPoint[] {
  const lastInLane = LANES.map(() => -Infinity);
  return [...points]
    .sort((a, b) => a.x - b.x)
    .map((point) => {
      const free = lastInLane.findIndex((last) => point.x - last >= LANE_DISTANCE);
      const lane = free === -1 ? lastInLane.indexOf(Math.min(...lastInLane)) : free;
      lastInLane[lane] = point.x;
      return { x: point.x, y: row + LANES[lane], count: point.rounds.length, rounds: point.rounds };
    });
}

function radius(context: ScriptableContext<'scatter'>): number {
  return ((context.raw as StripPoint | undefined)?.count ?? 1) > 1 ? MERGED_DOT_RADIUS : DOT_RADIUS;
}
