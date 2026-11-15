import { DatePipe, DecimalPipe, formatNumber } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, LOCALE_ID, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { Message } from 'primeng/message';
import { Tag } from 'primeng/tag';
import { TableModule } from 'primeng/table';
import { GameDetailDto } from '../../dto/game-detail.dto';
import { GAME_STATUS_LABELS, GAME_STATUS_SEVERITIES, isResumable } from '../../models/game-filter';
import { CHECKOUT_MODES } from '../../models/checkout-mode';
import { finishOf, modeOf, playOf } from '../../models/game-settings';
import { countsPoints, variantLabel } from '../../models/game-variant';
import {
  CLOCK_ZONES,
  KILLER_ZONES,
  TRAINING_GOALS,
  TRAINING_RINGS,
  fieldLabel,
  optionLabel,
  scoringLabel,
} from '../../models/variant-options';
import { activeGameId } from '../../services/active-game';
import { GameHistoryService } from '../../services/game-history.service';
import { GameReplayComponent } from '../game-replay/game-replay.component';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { ConfirmService } from '../../../../core/view/services/confirm.service';
import { SHORT_DATE_TIME } from '../../../../core/i18n/models/date-format';

const GAME_FIGURES = ['average', 'firstNine', 'darts', 'bestVisit', 'grouping'] as const;
const CHECKOUT_FIGURES = ['checkout', 'doubleDistance', 'busts'] as const;

type Figure = (typeof GAME_FIGURES)[number] | (typeof CHECKOUT_FIGURES)[number];

/** One row of a variant's figures: its label and one value per player. */
interface VariantRow {
  readonly label: string;
  readonly values: readonly string[];
}

/** One row of the figures table and the subheading it sits under. */
interface FigureRow {
  readonly figure: Figure;
  readonly group: string;
}

function sum(values: readonly number[]): number {
  return values.reduce((total, value) => total + value, 0);
}

/** A visit index from the query params; null for none or one that is no index. */
function visitParam(raw: string | null): number | null {
  const visit = raw === null ? NaN : Number(raw);
  return Number.isInteger(visit) && visit >= 0 ? visit : null;
}

@Component({
  selector: 'app-game-detail',
  imports: [
    BackLinkComponent,
    Button,
    DatePipe,
    DecimalPipe,
    GameReplayComponent,
    LoadingStateComponent,
    EmptyStateComponent,
    LoadErrorComponent,
    Message,
    RouterLink,
    TableModule,
    Tag,
  ],
  templateUrl: './game-detail.component.html',
  styleUrl: './game-detail.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameDetailComponent {
  private readonly history = inject(GameHistoryService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly confirm = inject(ConfirmService);
  private readonly locale = inject(LOCALE_ID);

  protected readonly detail = signal<GameDetailDto | null>(null);
  protected readonly loading = signal(true);
  protected readonly missing = signal(false);
  protected readonly failed = signal(false);
  protected readonly statusLabels = GAME_STATUS_LABELS;
  protected readonly statusSeverities = GAME_STATUS_SEVERITIES;
  /** The visit a link asked to open the replay on. */
  protected readonly startVisit = visitParam(this.route.snapshot.queryParamMap.get('visit'));

  protected readonly resumable = computed(() => {
    const detail = this.detail();
    return detail !== null && isResumable(detail.status);
  });
  protected readonly resuming = signal(false);
  protected readonly hidden = computed(() => this.detail()?.status === 'discarded');
  protected readonly hiding = signal(false);
  /** What went wrong with the last resume or show/hide, under the heading. */
  protected readonly actionError = signal<string | null>(null);

  protected readonly isElimination = computed(() => this.detail()?.game.settings.variant === 'elimination');
  protected readonly shortDateTime = SHORT_DATE_TIME;
  protected readonly showLabel = $localize`:@@game.detail.show:Wieder einblenden`;
  protected readonly hideLabel = $localize`:@@game.detail.hide:Für dich ausblenden`;

  protected readonly variantLabel = computed(() => {
    const variant = this.detail()?.game.settings.variant;
    return variant === undefined ? '' : variantLabel(variant);
  });

  /** The starting score of a points game; null for the other variants. */
  protected readonly mode = computed(() => {
    const game = this.detail()?.game;
    return game === undefined ? null : modeOf(game.settings);
  });

  /** Whether the game ran on points, with the x01 figures; the other variants have their own. */
  protected readonly countsPoints = computed(() => {
    const variant = this.detail()?.game.settings.variant;
    return variant !== undefined && countsPoints(variant);
  });

  /** How the game finished, or for the other variants the settings it was played with. */
  protected readonly settingsLabel = computed(() => {
    const game = this.detail()?.game;
    if (game === undefined) {
      return '';
    }
    const settings = game.settings;
    if (settings.variant === 'cricket') {
      return scoringLabel(settings.scoring);
    }
    if (settings.variant === 'killer') {
      const lives = $localize`:@@game.detail.lives:${settings.lives}:count: Leben`;
      return `${lives}, ${optionLabel(KILLER_ZONES, settings.zone)}`;
    }
    if (settings.variant === 'training') {
      const goal = optionLabel(TRAINING_GOALS, settings.goal);
      const detail = {
        free: [],
        random: [optionLabel(TRAINING_RINGS, settings.ring)],
        fields: [settings.fields.map(fieldLabel).join(' ')],
      }[settings.goal];
      const repeats = settings.goal !== 'free' && settings.repeats > 1 ? [`${settings.repeats}×`] : [];
      return [goal, ...detail, ...repeats].join(', ');
    }
    const { catchUp, playOn } = finishOf(settings);
    const finish = [
      ...(catchUp ? [$localize`:@@game.new.catchUp:Mit Nachziehen`] : []),
      ...(playOn ? [$localize`:@@game.new.playOn:Plätze ausspielen`] : []),
    ];
    if (settings.variant === 'around_the_clock') {
      const zone = optionLabel(CLOCK_ZONES, settings.zone);
      const skip = settings.skip ? [$localize`:@@game.detail.skip:mit Springen`] : [];
      return [zone, ...skip, ...finish].join(', ');
    }
    const checkout = optionLabel(CHECKOUT_MODES, settings.checkoutMode);
    const kill = settings.variant === 'elimination' && settings.kill === 'double' ? ['Double Kill'] : [];
    return [checkout, ...kill, ...finish].join(', ');
  });

  /** Each player's result in the variant's own terms, in seat order: a value and its unit. */
  protected readonly results = computed<readonly { value: string; unit: string }[]>(() => {
    const game = this.detail()?.game;
    if (game === undefined) {
      return [];
    }
    const play = playOf(game);
    return game.players.map((player, seat) => {
      if (play.variant === 'cricket') {
        const own = play.standing.players[seat];
        const closed = own.marks.filter((marks) => marks >= 3).length;
        return play.settings.scoring === 'no_score'
          ? { value: `${closed}/${own.marks.length}`, unit: $localize`:@@game.detail.closed:zu` }
          : { value: `${own.points}`, unit: $localize`:@@game.detail.points:Punkte` };
      }
      if (play.variant === 'killer') {
        return { value: `${play.standing.players[seat].lives}`, unit: $localize`:@@game.scoreboard.lives:Leben` };
      }
      if (play.variant === 'training') {
        const own = play.standing.players[seat];
        return play.settings.goal === 'free'
          ? { value: player.average === null ? '–' : formatNumber(player.average, this.locale, '1.1-1'), unit: 'Ø' }
          : { value: `${own.hits}/${own.darts}`, unit: $localize`:@@game.detail.hits:Treffer` };
      }
      if (play.variant === 'around_the_clock') {
        return { value: `${play.standing.players[seat].done}/21`, unit: $localize`:@@game.detail.fields:Felder` };
      }
      return play.variant === 'elimination'
        ? { value: `${player.remaining}`, unit: $localize`:@@game.detail.missingPoints:fehlen` }
        : { value: `${player.remaining}`, unit: $localize`:@@game.detail.remaining:Rest` };
    });
  });

  /** The figures of Cricket, Killer and Around the Clock, compared per player. */
  protected readonly variantRows = computed<VariantRow[]>(() => {
    const detail = this.detail();
    if (detail === null) {
      return [];
    }
    const { game, visits } = detail;
    const darts = game.players.map((player) =>
      sum(visits.filter((visit) => visit.playerId === player.id).map((visit) => visit.darts.length)),
    );
    const dartsRow = { label: 'Darts', values: darts.map((count) => `${count}`) };
    const number = (value: number | null, digits: string) =>
      value === null ? '–' : formatNumber(value, this.locale, digits);
    const play = playOf(game);
    if (play.variant === 'cricket') {
      const players = play.standing.players;
      const rows: VariantRow[] = [
        dartsRow,
        { label: 'MPR', values: players.map((player) => number(player.marksPerRound, '1.2-2')) },
        {
          label: $localize`:@@game.detail.closedTargets:Geschlossen`,
          values: players.map((player) => `${player.marks.filter((marks) => marks >= 3).length}/7`),
        },
      ];
      return play.settings.scoring === 'no_score'
        ? rows
        : [...rows, { label: $localize`:@@game.detail.points:Punkte`, values: players.map((p) => `${p.points}`) }];
    }
    if (play.variant === 'killer') {
      const players = play.standing.players;
      return [
        dartsRow,
        { label: $localize`:@@game.detail.livesLeft:Leben übrig`, values: players.map((p) => `${p.lives}`) },
        { label: $localize`:@@game.scoreboard.kills:Abschüsse`, values: players.map((p) => `${p.kills}`) },
      ];
    }
    if (play.variant === 'training') {
      const players = play.standing.players;
      if (play.settings.goal === 'free') {
        return [dartsRow, { label: 'Ø', values: game.players.map((player) => number(player.average, '1.1-1')) }];
      }
      const rate = (hits: number, thrown: number) =>
        thrown === 0 ? '–' : `${hits}/${thrown} (${number((100 * hits) / thrown, '1.0-0')} %)`;
      const fields = [...new Set(players.flatMap((player) => player.tallies.map(fieldLabel)))];
      return [
        dartsRow,
        {
          label: $localize`:@@game.scoreboard.hitRateLong:Trefferquote`,
          values: players.map((player) => rate(player.hits, player.darts)),
        },
        ...fields.map((field) => ({
          label: field,
          values: players.map((player) => {
            const tally = player.tallies.find((entry) => fieldLabel(entry) === field);
            return tally === undefined ? '–' : rate(tally.hits, tally.darts);
          }),
        })),
      ];
    }
    if (play.variant === 'around_the_clock') {
      const players = play.standing.players;
      return [
        dartsRow,
        { label: $localize`:@@game.detail.hits:Treffer`, values: players.map((p) => `${p.hits}`) },
        {
          label: $localize`:@@game.scoreboard.hitRateLong:Trefferquote`,
          values: players.map((p) => (p.darts === 0 ? '–' : `${number((100 * p.hits) / p.darts, '1.0-0')} %`)),
        },
      ];
    }
    return [];
  });

  /** Minutes of actual play, while that is known. */
  protected readonly durationMinutes = computed(() => {
    const seconds = this.detail()?.playedSeconds;
    return seconds === null || seconds === undefined ? null : Math.max(1, Math.round(seconds / 60));
  });

  /** Players with their figures, in the order they threw. */
  protected readonly standings = computed(() => {
    const detail = this.detail();
    if (!detail) {
      return [];
    }
    const { game, statistics, visits } = detail;
    // The x01 figures; the other variants come without, and read `results` instead.
    return game.players.map((player, seat) => ({
      ...player,
      won: player.id === game.winnerId,
      statistics: statistics[seat],
      busts: visits.filter((visit) => visit.playerId === player.id && visit.busted).length,
      doublesLocated: sum(statistics[seat]?.doubles.map((double) => double.located) ?? []),
      doublesThrown: sum(statistics[seat]?.doubles.map((double) => double.darts) ?? []),
    }));
  });

  constructor() {
    void this.load();
  }

  /** The figures compared per player, grouped; elimination has no checkout, so busts join the game. */
  protected readonly figureRows = computed<FigureRow[]>(() => {
    const group = $localize`:@@common.nav.game:Spiel`;
    const game = GAME_FIGURES.map((figure) => ({ figure, group }));
    return this.isElimination()
      ? [...game, { figure: 'busts', group }]
      : [...game, ...CHECKOUT_FIGURES.map((figure) => ({ figure, group: 'Checkout' }))];
  });

  protected confirmResume(): void {
    this.confirm.ask(
      $localize`:@@game.detail.resumeTitle:Spiel fortsetzen?`,
      $localize`:@@game.detail.resumeText:Das Spiel läuft danach wieder und zählt erst in die Statistik, wenn es beendet ist.`,
      $localize`:@@game.detail.resumeAction:Fortsetzen`,
      () => void this.resume(),
      true,
    );
  }

  /** Takes the game up again and goes into it, joining it first unless this device has it open. */
  private async resume(): Promise<void> {
    const gameId = this.detail()?.game.id;
    if (!gameId) {
      return;
    }
    this.resuming.set(true);
    this.actionError.set(null);
    try {
      await this.history.resume(gameId);
      await this.router.navigate(activeGameId() === gameId ? ['/game'] : ['/game/join', gameId]);
    } catch (failure) {
      this.actionError.set(
        httpErrorMessage(
          failure,
          { 404: $localize`:@@game.detail.resumeGone:Dieses Spiel ist schon vorbei und lässt sich nicht fortsetzen.` },
          $localize`:@@game.detail.resumeFailed:Das Spiel konnte nicht fortgesetzt werden.`,
        ),
      );
    } finally {
      this.resuming.set(false);
    }
  }

  protected confirmToggleHidden(): void {
    if (this.hidden()) {
      this.confirm.ask(
        $localize`:@@game.detail.showTitle:Wieder einblenden?`,
        $localize`:@@game.detail.showText:Das Spiel steht wieder in deiner Spieleliste und zählt in deine Statistik, sobald es beendet ist.`,
        $localize`:@@game.detail.showAction:Einblenden`,
        () => void this.toggleHidden(),
        true,
      );
    } else {
      this.confirm.ask(
        $localize`:@@game.detail.hideTitle:Für dich ausblenden?`,
        $localize`:@@game.detail.hideText:Das Spiel zählt nicht mehr in deine Statistik und verschwindet aus deiner Spieleliste, bis du nach „ausgeblendet“ filterst. Für die anderen Spieler ändert sich nichts. Du kannst es hier jederzeit wieder einblenden.`,
        $localize`:@@game.detail.hideAction:Ausblenden`,
        () => void this.toggleHidden(),
        true,
      );
    }
  }

  /** Hides the game for this account or shows it again, then reads its new status. */
  private async toggleHidden(): Promise<void> {
    const gameId = this.detail()?.game.id;
    if (!gameId) {
      return;
    }
    this.hiding.set(true);
    this.actionError.set(null);
    try {
      await this.history.setCounted(gameId, this.hidden());
      this.detail.set(await this.history.detail(gameId));
    } catch (failure) {
      this.actionError.set(
        httpErrorMessage(failure, {}, $localize`:@@game.detail.changeFailed:Das Spiel konnte nicht geändert werden.`),
      );
    } finally {
      this.hiding.set(false);
    }
  }

  protected rate(hits: number, attempts: number): number | null {
    return attempts === 0 ? null : hits / attempts;
  }

  protected async load(): Promise<void> {
    const gameId = this.route.snapshot.paramMap.get('gameId') ?? '';
    this.loading.set(true);
    this.failed.set(false);
    try {
      this.detail.set(await this.history.detail(gameId));
    } catch (failure) {
      if (failure instanceof HttpErrorResponse && failure.status === 404) {
        this.missing.set(true);
      } else {
        this.failed.set(true);
      }
    } finally {
      this.loading.set(false);
    }
  }
}
