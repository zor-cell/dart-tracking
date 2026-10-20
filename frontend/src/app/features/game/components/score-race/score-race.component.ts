import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import type {
  ChartData,
  ChartOptions,
  Plugin,
  ScriptableContext,
  ScriptableLineSegmentContext,
} from 'chart.js';
import { UIChart } from 'primeng/chart';
import { PlayerDto } from '../../dto/player.dto';
import { VisitDto } from '../../dto/visit.dto';
import { GameMode } from '../../models/game-mode';
import { GameVariant } from '../../models/game-variant';
import { DARTS_PER_TURN, labelPoints, ReplayPosition } from '../../models/visit';
import {
  chartTheme,
  crosshairPlugin,
  endLabelsPlugin,
  indexMarkerPlugin,
} from '../../../../core/charts/models/chart-plugins';
import { SERIES_COLORS } from '../../../../core/charts/models/series-colors';

/** A dart slot on the race: the standing after it, and the dart thrown there, if any. */
interface RacePoint {
  readonly x: number;
  readonly y: number;
  readonly dart?: string;
  readonly bust?: boolean;
  /** Not thrown: the game ended before this player's visit. */
  readonly idle?: boolean;
}

function pointOf(context: ScriptableContext<'line'>): RacePoint {
  return (context.raw ?? { x: 0, y: 0 }) as RacePoint;
}

/** "Runde 3 · Dart 2" for a slot index past the start. */
function slotTitle(index: number): string {
  return `Runde ${Math.ceil(index / DARTS_PER_TURN)} · Dart ${((index - 1) % DARTS_PER_TURN) + 1}`;
}

function slotLabel(name: string, point: RacePoint): string {
  return `${name}: ${point.dart}${point.bust ? ' (Bust)' : ''}`;
}

/**
 * Every player's progress dart by dart, the goal at the top: points still
 * needed in x01, points gathered in elimination.
 */
@Component({
  selector: 'app-score-race',
  imports: [UIChart],
  templateUrl: './score-race.component.html',
  styleUrl: './score-race.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ScoreRaceComponent {
  readonly visits = input.required<readonly VisitDto[]>();
  readonly players = input.required<readonly PlayerDto[]>();
  readonly mode = input.required<GameMode>();
  readonly variant = input.required<GameVariant>();
  /** How far a replay has got; null shows the whole game unmarked. */
  readonly position = input<ReplayPosition | null>(null);
  /** The player to bring forward; the others fade. */
  readonly highlightId = input<number | null>(null);

  private readonly theme = chartTheme(inject(DOCUMENT));
  protected readonly plugins: Plugin<'line'>[] = [
    crosshairPlugin,
    endLabelsPlugin,
    indexMarkerPlugin(() => this.markerX()),
  ];

  private readonly elimination = computed(() => this.variant() === 'elimination');
  private readonly seats = computed(() => this.players().length);
  private readonly totalRounds = computed(() => Math.ceil(this.visits().length / this.seats()));

  /** Visits finished at the current position, in throwing order. */
  private readonly finishedVisits = computed(() => {
    const position = this.position();
    if (position === null) {
      return this.visits().length;
    }
    const visit = this.visits()[position.visit];
    return visit !== undefined && position.dart === visit.darts.length - 1
      ? position.visit + 1
      : position.visit;
  });

  /** Where on the round axis the replay stands: a third of a round per dart. */
  private readonly markerX = computed(() => {
    const position = this.position();
    if (position === null) {
      return null;
    }
    const round = Math.floor(position.visit / this.seats());
    // A finished visit closes its slot, even one that ended early on a checkout.
    const visit = this.visits()[position.visit];
    const finished = visit !== undefined && position.dart === visit.darts.length - 1;
    return round + (finished ? 1 : (position.dart + 1) / DARTS_PER_TURN);
  });

  /** The number plotted for a standing: what is left in x01, what is gathered in elimination. */
  private value(remaining: number): number {
    return this.elimination() ? this.mode() - remaining : remaining;
  }

  /** How many darts of the visit at `index` the replay has reached. */
  private shownDarts(index: number): number {
    const position = this.position();
    if (position === null || index < position.visit) {
      return this.visits()[index].darts.length;
    }
    return index === position.visit ? position.dart + 1 : 0;
  }

  /** One point per dart slot, three per round, so every series shares the same x per index. */
  private series(playerId: number): RacePoint[] {
    const visits = this.visits();
    const seats = this.seats();
    const points: RacePoint[] = [{ x: 0, y: this.value(this.mode()) }];
    for (let round = 0; round < this.totalRounds(); round++) {
      const first = round * seats;
      const index = visits.findIndex(
        (visit, at) => at >= first && at < first + seats && visit.playerId === playerId,
      );
      if (index === -1) {
        // The game ended before this player threw in the round: the score stands.
        if (this.finishedVisits() < visits.length) {
          break;
        }
        const y = this.value(visits[visits.length - 1].standings[playerId]);
        for (let slot = 1; slot <= DARTS_PER_TURN; slot++) {
          points.push({ x: round + slot / DARTS_PER_TURN, y, idle: true });
        }
        continue;
      }
      const visit = visits[index];
      const shown = this.shownDarts(index);
      let remaining = visits[index - 1]?.standings[playerId] ?? this.mode();
      visit.darts.slice(0, shown).forEach((dart, at) => {
        const last = at === visit.darts.length - 1;
        remaining = last ? visit.standings[playerId] : remaining - labelPoints(dart.label);
        points.push({
          x: round + (at + 1) / DARTS_PER_TURN,
          y: this.value(remaining),
          dart: dart.label,
          bust: last && visit.busted,
        });
      });
      if (shown < visit.darts.length) {
        break;
      }
      for (let slot = visit.darts.length + 1; slot <= DARTS_PER_TURN; slot++) {
        points.push({ x: round + slot / DARTS_PER_TURN, y: this.value(remaining) });
      }
    }
    return points;
  }

  protected readonly data = computed<ChartData<'line', RacePoint[]>>(() => {
    const highlight = this.highlightId();
    return {
      datasets: this.players().map((player) => {
        const base = SERIES_COLORS[player.id % SERIES_COLORS.length];
        const color = highlight === null || highlight === player.id ? base : `${base}40`;
        const points = this.series(player.id);
        return {
          label: player.name,
          data: points,
          segment: {
            borderDash: (segment: ScriptableLineSegmentContext) =>
              points[segment.p1DataIndex]?.idle ? [4, 4] : undefined,
          },
          borderColor: color,
          backgroundColor: color,
          borderWidth: 2,
          pointRadius: (context: ScriptableContext<'line'>) => (pointOf(context).bust ? 5 : 0),
          pointStyle: (context: ScriptableContext<'line'>) => (pointOf(context).bust ? 'crossRot' : 'circle'),
          pointBorderWidth: (context: ScriptableContext<'line'>) => (pointOf(context).bust ? 2 : 1),
          pointHoverRadius: 4,
          pointHoverBorderWidth: 2,
          pointHoverBorderColor: this.theme.surface,
          tension: 0,
          clip: 4,
        };
      }),
    };
  });

  protected readonly options = computed<ChartOptions<'line'>>(() => {
    const { text, muted, grid, surface, border, font } = this.theme;
    const elimination = this.elimination();
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      font: { family: font },
      interaction: { mode: 'index', intersect: false },
      layout: { padding: { right: 72 } },
      scales: {
        x: {
          type: 'linear',
          min: 0,
          max: this.totalRounds(),
          title: { display: true, text: 'Runde', color: muted, font: { family: font, size: 10 } },
          grid: { display: false },
          border: { display: false },
          ticks: { color: muted, font: { family: font, size: 10 }, stepSize: 1 },
        },
        y: {
          // The goal sits at the top: remaining 0 in x01, the target score in elimination.
          reverse: !elimination,
          min: 0,
          max: this.mode(),
          grid: { color: grid },
          border: { display: false },
          ticks: { color: muted, font: { family: font, size: 10 } },
          // Round steps only; the mode itself (501) would sit just above 500.
          afterBuildTicks: (scale) => {
            const step = this.mode() > 400 ? 100 : 50;
            scale.ticks = Array.from({ length: Math.floor(this.mode() / step) + 1 }, (_, i) => ({
              value: i * step,
            }));
          },
        },
      },
      plugins: {
        legend: {
          position: 'top',
          align: 'start',
          labels: {
            color: text,
            font: { family: font, size: 11 },
            boxWidth: 10,
            boxHeight: 10,
            useBorderRadius: true,
            borderRadius: 2,
            padding: 8,
          },
        },
        tooltip: {
          backgroundColor: surface,
          borderColor: border,
          borderWidth: 1,
          titleColor: muted,
          bodyColor: text,
          titleFont: { family: font, size: 11, weight: 'normal' },
          bodyFont: { family: font, size: 12 },
          padding: 8,
          boxWidth: 8,
          boxHeight: 8,
          boxPadding: 4,
          callbacks: {
            // No title on a slot without a dart, so no empty tooltip is drawn there.
            title: (items) => (items.length === 0 ? '' : slotTitle(items[0].dataIndex)),
            label: (item) => slotLabel(item.dataset.label ?? '', item.raw as RacePoint),
            labelColor: (item) => {
              const color = item.dataset.borderColor as string;
              return { borderColor: color, backgroundColor: color, borderWidth: 0, borderRadius: 2 };
            },
          },
          filter: (item) => (item.raw as RacePoint).dart !== undefined,
          // Closest to the goal first.
          itemSort: (a, b) => ((elimination ? -1 : 1) * ((a.parsed.y ?? 0) - (b.parsed.y ?? 0))),
        },
      },
    };
  });

  protected readonly ariaLabel = computed(() => {
    const standings = this.data()
      .datasets.map((set) => `${set.label} ${set.data.at(-1)?.y ?? ''}`)
      .join(', ');
    return `Verlauf über ${this.totalRounds()} Runden. Stand: ${standings}`;
  });
}
