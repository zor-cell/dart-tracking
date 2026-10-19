import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import type { ChartData, ChartOptions, Plugin } from 'chart.js';
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

/**
 * Every player's progress round by round, the goal at the top: points still
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

  /** Standings after each round, with the index of the visit that closed it. */
  private readonly rounds = computed(() => {
    const seats = this.players().length;
    const visits = this.visits();
    const rounds: { standings: readonly number[]; closedBy: number }[] = [
      { standings: this.players().map(() => this.mode()), closedBy: -1 },
    ];
    visits.forEach((visit, index) => {
      if (index % seats === seats - 1 || index === visits.length - 1) {
        rounds.push({ standings: visit.standings, closedBy: index });
      }
    });
    return rounds;
  });

  private readonly seats = computed(() => this.players().length);

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

  /** A player's points in the round under way: after their visit, or live during it. */
  private partial(playerId: number): { x: number; y: number } | null {
    const position = this.position();
    const finished = this.finishedVisits();
    const seats = this.seats();
    const visits = this.visits();
    if (position === null || position.dart < 0) {
      return null;
    }
    const round = Math.floor(position.visit / seats);
    // A round closed at this very dart is already among the completed ones.
    if (finished >= Math.min((round + 1) * seats, visits.length)) {
      return null;
    }
    for (let index = round * seats; index < Math.min((round + 1) * seats, visits.length); index++) {
      const visit = visits[index];
      if (visit.playerId !== playerId) {
        continue;
      }
      if (index < finished) {
        return { x: round + 1, y: this.value(visit.standings[playerId]) };
      }
      if (index === position.visit && position.dart >= 0) {
        const before = visits[index - 1]?.standings[playerId] ?? this.mode();
        const thrown = visit.darts.slice(0, position.dart + 1);
        const live = visit.busted ? before : before - thrown.reduce((sum, d) => sum + labelPoints(d.label), 0);
        return { x: round + thrown.length / DARTS_PER_TURN, y: this.value(live) };
      }
    }
    return null;
  }

  protected readonly data = computed<ChartData<'line', { x: number; y: number }[]>>(() => {
    const finished = this.finishedVisits();
    const highlight = this.highlightId();
    return {
      datasets: this.players().map((player) => {
        const base = SERIES_COLORS[player.id % SERIES_COLORS.length];
        const color = highlight === null || highlight === player.id ? base : `${base}40`;
        const points = this.rounds()
          .filter(({ closedBy }) => closedBy < finished)
          .map(({ standings }, round) => ({ x: round, y: this.value(standings[player.id]) }));
        const partial = this.partial(player.id);
        return {
          label: player.name,
          data: partial === null ? points : [...points, partial],
          borderColor: color,
          backgroundColor: color,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBorderWidth: 2,
          pointHoverBorderColor: this.theme.surface,
          tension: 0,
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
          max: this.rounds().length - 1,
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
            usePointStyle: true,
            pointStyle: 'line',
            boxWidth: 12,
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
            title: (items) => `Runde ${Math.ceil(items[0]?.parsed.x ?? 0)}`,
            labelColor: (item) => {
              const color = item.dataset.borderColor as string;
              return { borderColor: color, backgroundColor: color, borderWidth: 0, borderRadius: 2 };
            },
          },
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
    return `Verlauf über ${this.rounds().length - 1} Runden. Stand: ${standings}`;
  });
}
