import { Location } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterRenderEffect,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormArray,
  FormBuilder,
  FormControl,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AutoComplete, AutoCompleteCompleteEvent } from 'primeng/autocomplete';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { SelectButton } from 'primeng/selectbutton';
import { Skeleton } from 'primeng/skeleton';
import { Tag } from 'primeng/tag';
import { ToggleSwitch } from 'primeng/toggleswitch';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { centrePopoverArrow } from '../../../../core/view/models/popover-arrow';
import { Popover } from 'primeng/popover';
import { SetupBadge, setupBadges, setupName } from '../../models/setup-badges';
import {
  CHECKOUT_HINTS,
  CLOCK_ZONE_HINTS,
  KILLER_ZONE_HINTS,
  KILL_HINTS,
  SCORING_HINTS,
  TRAINING_GOAL_HINTS,
} from '../../models/setting-hints';
import { map } from 'rxjs';
import { SocketService } from '../../../../core/socket/services/socket.service';
import { AuthService } from '../../../auth/services/auth.service';
import { PlayerIdentityDto } from '../../../player/dto/player-identity.dto';
import { PlayerService } from '../../../player/services/player.service';
import { SettingsService } from '../../../settings/services/settings.service';
import { GAME_MODES, GameMode } from '../../models/game-mode';
import { CHECKOUT_MODES, CheckoutMode } from '../../models/checkout-mode';
import { GAME_SECTIONS, GAME_VARIANTS, GameVariant, variantLabel } from '../../models/game-variant';
import {
  CLOCK_ZONES,
  ELIMINATION_KILLS,
  EliminationKill,
  CRICKET_SCORINGS,
  ClockZone,
  CricketScoring,
  KILLER_LIVES,
  KILLER_ZONES,
  KillerZone,
  TRAINING_GOALS,
  TRAINING_REPEATS,
  TRAINING_RINGS,
  TrainingGoal,
  TrainingRing,
} from '../../models/variant-options';
import { standings } from '../../models/variant-standing';
import { GameConfigDto } from '../../dto/game-config.dto';
import { GameSettingsDto } from '../../dto/game-settings.dto';
import { QuickStartDto } from '../../dto/quick-start.dto';
import { PlayerDto } from '../../dto/player.dto';
import { PlayerSlotDto } from '../../dto/player-slot.dto';
import { GameService } from '../../services/game.service';
import { GameSessionService } from '../../services/game-session.service';
import { GameDraftService } from '../../services/game-draft.service';
import { GameDraft, Seat } from '../../models/game-draft';
import { FieldErrorComponent } from '../../../../core/view/components/field-error/field-error.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { GameRulesComponent } from '../game-rules/game-rules.component';
import { FieldPickerComponent } from '../field-picker/field-picker.component';
import { TrainingFieldDto } from '../../dto/training-settings.dto';
import {
  SortableListComponent,
  SortableMove,
} from '../../../../core/view/components/sortable-list/sortable-list.component';

@Component({
  selector: 'app-game-setup',
  imports: [
    ReactiveFormsModule,
    AutoComplete,
    Button,
    InputText,
    SelectButton,
    Skeleton,
    Tag,
    ToggleSwitch,
    InfoHintComponent,
    Popover,
    FieldErrorComponent,
    FieldPickerComponent,
    LoadingStateComponent,
    GameRulesComponent,
    SortableListComponent,
  ],
  templateUrl: './game-new.component.html',
  styleUrl: './game-new.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameNewComponent {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly game = inject(GameService);
  private readonly session = inject(GameSessionService);
  private readonly auth = inject(AuthService);
  private readonly players = inject(PlayerService);
  private readonly settings = inject(SettingsService);
  private readonly socket = inject(SocketService);
  private readonly location = inject(Location);
  private readonly drafts = inject(GameDraftService);

  protected readonly modeOptions = GAME_MODES.map((mode) => ({ label: `${mode}`, value: mode }));
  protected readonly sections = GAME_SECTIONS;
  protected readonly variantName = variantLabel;
  protected readonly checkoutModeOptions = [...CHECKOUT_MODES];
  protected readonly cricketScoringOptions = [...CRICKET_SCORINGS];
  protected readonly killerLivesOptions = KILLER_LIVES.map((lives) => ({ label: `${lives}`, value: lives }));
  protected readonly killerZoneOptions = [...KILLER_ZONES];
  protected readonly clockZoneOptions = [...CLOCK_ZONES];
  protected readonly eliminationKillOptions = [...ELIMINATION_KILLS];
  protected readonly checkoutHints = CHECKOUT_HINTS;
  protected readonly killHints = KILL_HINTS;
  protected readonly scoringHints = SCORING_HINTS;
  protected readonly killerZoneHints = KILLER_ZONE_HINTS;
  protected readonly clockZoneHints = CLOCK_ZONE_HINTS;
  protected readonly trainingGoalOptions = [...TRAINING_GOALS];
  protected readonly trainingRingOptions = [...TRAINING_RINGS];
  protected readonly trainingGoalHints = TRAINING_GOAL_HINTS;
  protected readonly trainingRepeatsOptions = TRAINING_REPEATS.map((hits) => ({ label: `${hits}`, value: hits }));
  protected readonly goalName = $localize`:@@game.new.goal:Ziel`;
  protected readonly scoringName = $localize`:@@game.new.scoring:Punkte`;
  protected readonly zoneName = $localize`:@@game.new.zone:Feld`;
  protected readonly hintLabel = (setting: string): string =>
    $localize`:@@game.new.hintLabel:Was die Optionen bei ${setting}:setting: bedeuten`;

  protected readonly signedIn = this.auth.isAuthenticated;
  /** One placeholder row per seat `restoreSeats` will open. */
  protected readonly skeletonSeats = [0];
  /** Rendered height of a seat's input and buttons, so the placeholders take the same space. */
  protected readonly seatRowHeight = '2.4375rem';
  /** Whether the session is known yet; the seats render only once it is. */
  protected readonly sessionResolved = signal(false);
  protected readonly suggestions = signal<PlayerIdentityDto[]>([]);
  protected readonly seatMessages = { required: $localize`:@@game.new.nameRequired:Bitte einen Namen eingeben.` };
  protected readonly formMessages = {
    groupSeats: $localize`:@@game.new.groupSeats:Wähle mindestens 2 Spieler.`,
  };

  protected readonly form = this.fb.group({
    mode: this.fb.nonNullable.control<GameMode>(501, Validators.required),
    variant: this.fb.nonNullable.control<GameVariant>('x01', Validators.required),
    checkoutMode: this.fb.nonNullable.control<CheckoutMode>('double_out', Validators.required),
    cricketScoring: this.fb.nonNullable.control<CricketScoring>('standard'),
    killerLives: this.fb.nonNullable.control(3),
    killerZone: this.fb.nonNullable.control<KillerZone>('double'),
    clockZone: this.fb.nonNullable.control<ClockZone>('any'),
    clockSkip: this.fb.nonNullable.control(false),
    eliminationKill: this.fb.nonNullable.control<EliminationKill>('any'),
    trainingGoal: this.fb.nonNullable.control<TrainingGoal>('free'),
    trainingRing: this.fb.nonNullable.control<TrainingRing>('single'),
    trainingFields: this.fb.nonNullable.control<readonly TrainingFieldDto[]>([]),
    trainingRepeats: this.fb.nonNullable.control(1),
    trainingShuffle: this.fb.nonNullable.control(false),
    catchUp: this.fb.nonNullable.control(false),
    playOn: this.fb.nonNullable.control(false),
    players: this.fb.array<FormControl<Seat>>([]),
  }, { validators: [groupSeats, trainingFields] });

  /** The finished game being replayed, once `restoreSeats` has confirmed it exists. */
  private rematchId: string | null = null;

  protected readonly variant = toSignal(this.form.controls.variant.valueChanges, {
    initialValue: this.form.controls.variant.value,
  });
  /** The seat controls as a new array on every change; the array itself is mutated in place. */
  protected readonly seatControls = toSignal(
    this.form.controls.players.valueChanges.pipe(map(() => [...this.seats.controls])),
    { initialValue: [] },
  );
  /** The game picked in the first step, kept in the URL so the back button returns to the list. */
  protected readonly chosen = toSignal(
    this.route.queryParamMap.pipe(map((params) => parseVariant(params.get('game')))),
    { initialValue: parseVariant(this.route.snapshot.queryParamMap.get('game')) },
  );
  private readonly heading = viewChild<ElementRef<HTMLElement>>('heading');
  private readonly seatList = viewChild(SortableListComponent);
  private readonly shuffleIcon = viewChild<ElementRef<SVGElement>>('shuffleIcon');
  /** Whether the list led here, so changing the game can step back instead of adding history. */
  private pickedHere = false;
  /** Whether changes are kept as the draft: from the restore on, never for a rematch. */
  private drafting = false;

  /** The setup played most, offered for one tap: undefined while it loads, null for none. */
  protected readonly quickStart = signal<QuickStartDto | null | undefined>(null);
  /** The own address-book entry, named "Du" in the quick start. */
  private readonly selfId = signal<string | null>(null);
  protected readonly starting = signal(false);
  protected readonly quickTitle = computed(() => {
    const quick = this.quickStart();
    return quick ? setupName(quick.settings) : '';
  });
  /** The quick start's settings that differ from the defaults. */
  protected readonly quickBadges = computed(() => {
    const quick = this.quickStart();
    return quick ? setupBadges(quick.settings) : [];
  });
  /** The badge whose explanation the popover shows. */
  protected readonly shownBadge = signal<SetupBadge | null>(null);
  protected readonly quickPlayers = computed(() =>
    (this.quickStart()?.players ?? [])
      .map((seat) => (seat.playerId !== null && seat.playerId === this.selfId() ? $localize`:@@player.list.self:Du` : seat.name))
      .join(', '),
  );
  protected readonly quickLabel = computed(
    () => {
      const setup = [this.quickTitle(), ...this.quickBadges().map((badge) => badge.title)].join(', ');
      return $localize`:@@game.new.quickStartLabel:Schnellstart: ${setup}:setup: mit ${this.quickPlayers()}:players:`;
    },
  );

  protected readonly rulesOpen = signal(false);
  protected readonly rulesVariant = signal<GameVariant>('x01');
  private readonly clockZone = toSignal(this.form.controls.clockZone.valueChanges, {
    initialValue: this.form.controls.clockZone.value,
  });
  protected readonly trainingGoal = toSignal(this.form.controls.trainingGoal.valueChanges, {
    initialValue: this.form.controls.trainingGoal.value,
  });
  protected readonly pickedFields = toSignal(this.form.controls.trainingFields.valueChanges, {
    initialValue: this.form.controls.trainingFields.value,
  });
  /** Skipping ahead needs singles to tell apart from doubles and triples. */
  protected readonly clockSkippable = computed(() => this.clockZone() === 'any');
  /** Whether everyone runs for the same goal, so a round can catch up and places follow. */
  protected readonly racing = computed(() => RACES.includes(this.variant()));
  /** Places after the winner need someone left to play for them. */
  protected readonly placesLeft = computed(() => this.seatControls().length > 2);

  constructor() {
    void this.restoreSeats();

    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      const variant = parseVariant(params.get('game'));
      if (variant !== null && variant !== this.form.controls.variant.value) {
        this.form.controls.variant.setValue(variant);
        this.form.controls.variant.markAsDirty();
      }
      this.saveDraft();
    });
    this.form.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => this.saveDraft());

    // A new step puts the focus, and with it the view, on its heading.
    let shown: HTMLElement | undefined;
    afterRenderEffect(() => {
      const heading = this.heading()?.nativeElement;
      if (shown !== undefined && heading !== undefined && heading !== shown) {
        heading.focus();
      }
      shown = heading ?? shown;
    });

    // Another device started the rematch first: join it instead of creating a second one.
    this.socket
      .on('rematch_started')
      .pipe(takeUntilDestroyed())
      .subscribe(() => {
        if (this.rematchId !== null) {
          void this.router.navigate(['/game']);
        }
      });
  }

  protected pickVariant(variant: GameVariant): void {
    this.pickedHere = true;
    void this.showStep(variant, false);
  }

  protected changeGame(): void {
    if (this.pickedHere) {
      this.pickedHere = false;
      this.location.back();
    } else {
      void this.showStep(null, true);
    }
  }

  private showStep(variant: GameVariant | null, replaceUrl: boolean): Promise<boolean> {
    return this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { game: variant },
      queryParamsHandling: 'merge',
      replaceUrl,
    });
  }

  protected readonly rulesLabel = (variant: GameVariant): string =>
    $localize`:@@game.new.rulesOf:Regeln für ${variantLabel(variant)}:game:`;

  protected openRules(variant: GameVariant): void {
    this.rulesVariant.set(variant);
    this.rulesOpen.set(true);
  }

  /** Opens the explanation of a quick start badge, or closes it on a second tap. */
  protected explainBadge(event: MouseEvent, badge: SetupBadge, popover: Popover): void {
    if (popover.overlayVisible && this.shownBadge() === badge) {
      popover.hide();
      return;
    }
    this.shownBadge.set(badge);
    popover.show(event, event.currentTarget);
  }

  protected readonly centreArrow = (popover: Popover) => centrePopoverArrow(popover);

  /** Start the setup played most at once, with its players. */
  protected startQuick(quick: QuickStartDto): void {
    this.create({
      ...quick,
      players: quick.players.map((seat) =>
        seat.playerId === null ? { name: seat.name } : { playerId: seat.playerId },
      ),
      evaluationEnabled: this.settings.evaluationEnabled(),
    });
  }

  protected get seats(): FormArray<FormControl<Seat>> {
    return this.form.controls.players;
  }

  protected addPlayer(): void {
    this.seats.push(this.createSeat(this.seats.length + 1));
  }

  protected removePlayer(index: number): void {
    if (this.seats.length > 1) {
      this.seats.removeAt(index);
    }
  }

  protected readonly seatName = (index: number): string =>
    $localize`:@@game.new.seatName:Spieler ${index + 1}:number:`;

  /** The identity a seat holds, or null for a typed name. */
  protected readonly seatIdentity = (seat: FormControl<Seat>): PlayerIdentityDto | null =>
    typeof seat.value === 'string' ? null : seat.value;

  protected readonly seatLabel = (seat: FormControl<Seat>, index: number): string =>
    this.label(seat.value) || this.seatName(index);

  private label(seat: Seat): string {
    return typeof seat === 'string' ? seat : seat.name;
  }

  /** Offer the address book, minus whoever already sits at another seat. */
  protected async completeSeat(event: AutoCompleteCompleteEvent): Promise<void> {
    const taken = new Set(
      this.seats.controls
        .map((control) => control.value)
        .filter((seat): seat is PlayerIdentityDto => typeof seat !== 'string')
        .map((identity) => identity.id),
    );
    const found = await this.players.search(event.query);
    this.suggestions.set(found.filter((identity) => !taken.has(identity.id)));
  }

  protected startGame(): void {
    if (this.form.invalid) {
      return;
    }
    const {
      mode, variant, checkoutMode, players, cricketScoring, killerLives, killerZone,
      clockZone, clockSkip, eliminationKill, catchUp, playOn,
      trainingGoal, trainingRing, trainingFields, trainingRepeats, trainingShuffle,
    } = this.form.getRawValue();
    const seats = (players as Seat[]).map<PlayerSlotDto>((seat) =>
      typeof seat === 'string' ? { name: seat.trim() } : { playerId: seat.id },
    );
    const finish = { catchUp: seats.length > 1 && catchUp, playOn: seats.length > 2 && playOn };
    const chosen: Record<GameVariant, GameSettingsDto> = {
      x01: { variant: 'x01', mode, checkoutMode, ...finish },
      elimination: { variant: 'elimination', mode, checkoutMode, kill: eliminationKill, ...finish },
      cricket: { variant: 'cricket', scoring: cricketScoring },
      killer: { variant: 'killer', lives: killerLives, zone: killerZone },
      around_the_clock: {
        variant: 'around_the_clock',
        zone: clockZone,
        skip: clockZone === 'any' && clockSkip,
        ...finish,
      },
      training: {
        variant: 'training',
        goal: trainingGoal,
        ring: trainingRing,
        fields: trainingGoal === 'fields' ? trainingFields : [],
        repeats: trainingGoal === 'free' ? 1 : trainingRepeats,
        shuffle: trainingGoal === 'fields' && trainingShuffle,
      },
    };
    this.create({
      settings: chosen[variant],
      players: seats,
      evaluationEnabled: this.settings.evaluationEnabled(),
      rematchOf: this.rematchId ?? undefined,
    });
  }

  private create(config: GameConfigDto): void {
    const rematchOf = config.rematchOf;
    this.starting.set(true);
    this.game
      .createGame(config)
      .subscribe({
        error: () => this.starting.set(false),
        next: () => {
          // A rematch keeps every device's role; a fresh game starts on the camera.
          if (rematchOf === undefined) {
            this.session.setRole('camera');
          }
          this.drafts.clear();
          void this.router.navigate(['/game']);
        },
      });
  }

  protected setTrainingFields(fields: readonly TrainingFieldDto[]): void {
    this.form.controls.trainingFields.setValue(fields);
    this.form.controls.trainingFields.markAsDirty();
  }

  /** Puts the seats in a random order, turning the icon and sliding the rows there. */
  protected shuffleSeats(): void {
    const order = shuffled(this.seats.controls);
    this.shuffleIcon()?.nativeElement.animate(
      [{ transform: 'rotate(0)' }, { transform: 'rotate(180deg)' }],
      { duration: 500, easing: 'cubic-bezier(0.2, 0, 0, 1)' },
    );
    this.seatList()?.animateReorder();
    this.seats.clear({ emitEvent: false });
    for (const seat of order) {
      this.seats.push(seat, { emitEvent: false });
    }
    this.seats.updateValueAndValidity();
  }

  protected moveSeat({ from, to }: SortableMove): void {
    const seat = this.seats.at(from);
    this.seats.removeAt(from);
    this.seats.insert(to, seat);
  }

  /** Seat the previous game's players, ranked, for a rematch; otherwise the account
   * itself first — the one player who is always there. */
  private async restoreSeats(): Promise<void> {
    await this.auth.ready;

    const rematchId = this.route.snapshot.queryParamMap.get('rematch');
    const previous = rematchId ? await this.game.fetch(rematchId) : null;
    this.rematchId = previous?.id ?? null;

    if (previous !== null) {
      this.form.patchValue(formValues(previous.settings));
      if (this.chosen() === null) {
        await this.showStep(previous.settings.variant, true);
      }
      // Worst finish throws first, the winner last.
      const ranks = standings(previous, (value) => `${value}`).map((standing) => standing.rank);
      const order = previous.players
        .map((player, seat) => ({ player, rank: ranks[seat] }))
        .sort((a, b) => a.rank - b.rank)
        .map(({ player }) => player);
      const own = this.signedIn()
        ? await this.players.owned(order.map((player) => player.identityId))
        : [];
      for (const player of order) {
        this.seats.push(this.fb.nonNullable.control<Seat>(reseat(player, own), Validators.required));
      }
    } else {
      if (this.signedIn()) {
        this.quickStart.set(undefined);
        void this.game.quickStart().then((quick) => this.quickStart.set(quick));
      }
      const self = this.signedIn()
        ? (await this.players.search('')).find((identity) => identity.isSelf)
        : undefined;
      this.selfId.set(self?.id ?? null);

      const draft = this.drafts.read(this.account());
      if (draft !== null) {
        await this.resume(draft);
      } else {
        this.seats.push(self ? this.fb.nonNullable.control<Seat>(self) : this.createSeat(1));
      }
      this.drafting = true;
      this.saveDraft();
    }
    this.sessionResolved.set(true);
  }

  /** Pick up the setup left here earlier; a game named in the URL wins over its pick. */
  private async resume(draft: GameDraft): Promise<void> {
    const chosen = this.chosen();
    this.form.patchValue({ ...draft.settings, ...(chosen !== null && { variant: chosen }) });
    for (const seat of draft.seats) {
      this.seats.push(this.fb.nonNullable.control<Seat>(seat, Validators.required));
    }
    if (chosen === null && draft.chosen !== null) {
      await this.showStep(draft.chosen, true);
    }
  }

  private saveDraft(): void {
    if (!this.drafting) {
      return;
    }
    const { players, ...settings } = this.form.getRawValue();
    this.drafts.save({ account: this.account(), chosen: this.chosen(), settings, seats: players });
  }

  private account(): string | null {
    return this.auth.user()?.id ?? null;
  }

  /** Signed out there is no address book, so a placeholder name saves typing;
   * signed in an empty seat is the prompt to pick someone. */
  private createSeat(position: number): FormControl<Seat> {
    return this.fb.nonNullable.control<Seat>(
      this.signedIn() ? '' : $localize`:@@game.new.seatName:Spieler ${position}:number:`,
      Validators.required,
    );
  }
}

/** The games where everyone runs for the same goal. */
const RACES: readonly GameVariant[] = ['x01', 'elimination', 'around_the_clock'];

function parseVariant(value: string | null): GameVariant | null {
  return GAME_VARIANTS.find((option) => option.value === value)?.value ?? null;
}

/** Killer and Elimination need someone to knock out or reset. */
function groupSeats(form: AbstractControl): ValidationErrors | null {
  const variant = form.get('variant')?.value as GameVariant | undefined;
  const seats = (form.get('players') as FormArray | null)?.length ?? 0;
  return (variant === 'killer' || variant === 'elimination') && seats < 2 ? { groupSeats: true } : null;
}

/** A training on own fields needs at least one. */
function trainingFields(form: AbstractControl): ValidationErrors | null {
  const fields = form.get('trainingFields')?.value as readonly TrainingFieldDto[] | undefined;
  const chosen =
    form.get('variant')?.value !== 'training' ||
    form.get('trainingGoal')?.value !== 'fields' ||
    (fields?.length ?? 0) > 0;
  return chosen ? null : { trainingFields: true };
}

/** A copy of the items in random order (Fisher–Yates). */
function shuffled<T>(items: readonly T[]): T[] {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

/** A game's settings as values of the form; what the variant does not use stays as is. */
function formValues(settings: GameSettingsDto) {
  const finish = 'catchUp' in settings ? { catchUp: settings.catchUp, playOn: settings.playOn } : {};
  switch (settings.variant) {
    case 'x01':
      return { variant: settings.variant, mode: settings.mode, checkoutMode: settings.checkoutMode, ...finish };
    case 'elimination':
      return {
        variant: settings.variant,
        mode: settings.mode,
        checkoutMode: settings.checkoutMode,
        eliminationKill: settings.kill,
        ...finish,
      };
    case 'cricket':
      return { variant: settings.variant, cricketScoring: settings.scoring };
    case 'killer':
      return { variant: settings.variant, killerLives: settings.lives, killerZone: settings.zone };
    case 'around_the_clock':
      return { variant: settings.variant, clockZone: settings.zone, clockSkip: settings.skip, ...finish };
    case 'training':
      return {
        variant: settings.variant,
        trainingGoal: settings.goal,
        trainingRing: settings.ring,
        trainingFields: settings.fields,
        trainingRepeats: settings.repeats,
        trainingShuffle: settings.shuffle,
      };
  }
}

/** The identity behind a previous seat: this account's address-book entry if
 * it has one, otherwise the seat itself, which the server accepts for a rematch. */
function reseat(player: PlayerDto, own: readonly PlayerIdentityDto[]): Seat {
  return (
    own.find((identity) => identity.id === player.identityId) ?? {
      id: player.identityId,
      name: player.name,
      isSelf: false,
      linked: false,
    }
  );
}
