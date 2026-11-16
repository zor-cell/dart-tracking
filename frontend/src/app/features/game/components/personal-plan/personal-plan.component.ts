import { formatNumber } from '@angular/common';
import { ChangeDetectionStrategy, Component, LOCALE_ID, computed, inject, input, signal } from '@angular/core';
import { ProgressBar } from 'primeng/progressbar';
import { Skeleton } from 'primeng/skeleton';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { PersonalPlanDto, PlannedFieldDto } from '../../dto/personal-plan.dto';
import { blockLabel, blockSeconds, durationLabel, hitRate } from '../../models/personal-blocks';
import { PersonalFocus, PersonalLength, fieldLabel } from '../../models/variant-options';
import { GameService } from '../../services/game.service';

/** One weak field as the list shows it. */
interface FieldRow {
  readonly label: string;
  readonly rate: string;
  readonly average: string;
  readonly hint: string;
  /** Bar length and the average's mark, in percent; the full bar is 100 %. */
  readonly bar: number;
  readonly mark: number;
}

/** What the personal training's plan is drawn from, and the plan it would start on. */
@Component({
  selector: 'app-personal-plan',
  imports: [InfoHintComponent, LoadErrorComponent, ProgressBar, Skeleton],
  templateUrl: './personal-plan.component.html',
  styleUrl: './personal-plan.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PersonalPlanComponent {
  private readonly games = inject(GameService);
  private readonly locale = inject(LOCALE_ID);

  readonly focus = input.required<PersonalFocus>();
  readonly length = input.required<PersonalLength>();
  /** Minutes a timed plan runs; null when it is played by darts. */
  readonly minutes = input<number | null>(null);

  protected readonly plan = signal<PersonalPlanDto | null>(null);
  protected readonly failed = signal(false);
  protected readonly weaknessesLabel = $localize`:@@game.personal.weaknesses:Deine Schwächen`;

  /** The plan of the picked focus; the weak fields stay the same for every length. */
  private readonly picked = computed(() => this.plan()?.foci.find((entry) => entry.focus === this.focus()) ?? null);

  protected readonly source = computed(() => {
    const plan = this.plan();
    if (plan === null) {
      return '';
    }
    if (plan.darts === 0) {
      return $localize`:@@game.personal.noRecord:Noch keine Darts auf Zielfelder. Das erste Training lernt deine Felder kennen.`;
    }
    const darts = formatNumber(plan.darts, this.locale);
    return $localize`:@@game.personal.source:Aus deinen letzten ${plan.games}:games: Spielen mit Zielfeldern, ${darts}:darts: Darts`;
  });

  protected readonly fields = computed(() => (this.picked()?.fields ?? []).map((field) => this.row(field)));

  /** The plan's size beside its title: "90 Darts", or "15 min" when timed. */
  protected readonly size = computed(() => {
    const minutes = this.minutes();
    return minutes === null ? `${this.length()} Darts` : `${minutes} min`;
  });

  protected readonly blocks = computed(() => {
    const blocks = this.picked()?.lengths.find((entry) => entry.length === this.length())?.blocks ?? [];
    const minutes = this.minutes();
    const seconds = minutes === null ? null : blockSeconds(blocks, minutes);
    return blocks.map((block, index) => ({
      label: blockLabel(block),
      size: seconds === null ? `${block.darts} Darts` : durationLabel(seconds[index]),
    }));
  });

  constructor() {
    this.load();
  }

  protected load(): void {
    this.failed.set(false);
    this.plan.set(null);
    this.games.personalPlan().subscribe({
      next: (plan) => this.plan.set(plan),
      error: () => this.failed.set(true),
    });
  }

  private row(field: PlannedFieldDto): FieldRow {
    const rate = hitRate(field.hits, field.darts);
    const average = hitRate(field.ringHits, field.ringDarts);
    const percent = (value: number | null) => (value === null ? '–' : `${formatNumber(value, this.locale, '1.0-0')} %`);
    const hint = field.telling
      ? $localize`:@@game.personal.darts:${field.darts}:count: Darts`
      :$localize`:@@game.personal.thin:Noch wenig Darts (${field.darts}:count:)`;
    return {
      label: fieldLabel(field),
      rate: percent(rate),
      average: percent(average),
      hint,
      bar: rate ?? 0,
      mark: average ?? 0,
    };
  }
}
