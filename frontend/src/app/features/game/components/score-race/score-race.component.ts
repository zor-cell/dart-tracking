import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import type { ChartData, ChartOptions, Plugin } from 'chart.js';
import { UIChart } from 'primeng/chart';
import { PlayerDto } from '../../dto/player.dto';
import { VisitDto } from '../../dto/visit.dto';
import { GameMode } from '../../models/game-mode';
import { GameVariant } from '../../models/game-variant';
import { chartTheme, crosshairPlugin, endLabelsPlugin } from '../../../../core/charts/models/chart-plugins';
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

  private readonly theme = chartTheme(inject(DOCUMENT));
  protected readonly plugins: Plugin<'line'>[] = [crosshairPlugin, endLabelsPlugin];

  private readonly elimination = computed(() => this.variant() === 'elimination');

  /** Standings after each completed round, starting with everyone at the mode. */
  private readonly rounds = computed(() => {
    const seats = this.players().length;
    const visits = this.visits();
    const rounds: (readonly number[])[] = [this.players().map(() => this.mode())];
    visits.forEach((visit, index) => {
      if (index % seats === seats - 1 || index === visits.length - 1) {
        rounds.push(visit.standings);
      }
    });
    return rounds;
  });

  protected readonly unitLabel = computed(() =>
    this.elimination() ? 'Punkte nach jeder Runde' : 'Restpunkte nach jeder Runde',
  );

  protected readonly data = computed<ChartData<'line'>>(() => {
    const rounds = this.rounds();
    const mode = this.mode();
    const elimination = this.elimination();
    return {
      labels: rounds.map((_, round) => round),
      datasets: this.players().map((player) => {
        const color = SERIES_COLORS[player.id % SERIES_COLORS.length];
        return {
          label: player.name,
          data: rounds.map((standings) =>
            elimination ? mode - standings[player.id] : standings[player.id],
          ),
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
          title: { display: true, text: 'Runde', color: muted, font: { family: font, size: 10 } },
          grid: { display: false },
          border: { display: false },
          ticks: { color: muted, font: { family: font, size: 10 } },
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
            title: (items) => `Runde ${items[0]?.label ?? ''}`,
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
    const finals = this.data()
      .datasets.map((set) => `${set.label} ${set.data[set.data.length - 1]}`)
      .join(', ');
    return `Verlauf über ${this.rounds().length - 1} Runden. Endstand: ${finals}`;
  });
}
