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
import { map } from 'rxjs';
import { SocketService } from '../../../../core/socket/services/socket.service';
import { AuthService } from '../../../auth/services/auth.service';
import { PlayerIdentityDto } from '../../../player/dto/player-identity.dto';
import { PlayerService } from '../../../player/services/player.service';
import { SettingsService } from '../../../settings/services/settings.service';
import { GAME_MODES, GameMode } from '../../models/game-mode';
import { CHECKOUT_MODES, CheckoutMode } from '../../models/checkout-mode';
import { GAME_VARIANTS, GameVariant, variantLabel } from '../../models/game-variant';
import { GAME_RULES } from '../../models/game-rules';
import {
  CLOCK_ZONES,
  CRICKET_SCORINGS,
  ClockZone,
  CricketScoring,
  KILLER_LIVES,
  KILLER_ZONES,
  KillerZone,
  optionLabel,
  scoringLabel,
} from '../../models/variant-options';
import { standings } from '../../models/variant-standing';
import { GameConfigDto } from '../../dto/game-config.dto';
import { GameStateDto } from '../../dto/game-state.dto';
import { QuickStartDto } from '../../dto/quick-start.dto';
import { PlayerDto } from '../../dto/player.dto';
import { PlayerSlotDto } from '../../dto/player-slot.dto';
import { GameService } from '../../services/game.service';
import { GameSessionService } from '../../services/game-session.service';
import { FieldErrorComponent } from '../../../../core/view/components/field-error/field-error.component';
import { GameRulesComponent } from '../game-rules/game-rules.component';
import {
  SortableListComponent,
  SortableMove,
} from '../../../../core/view/components/sortable-list/sortable-list.component';

/** What a seat holds: a known identity, or the name typed for a guest. */
type Seat = PlayerIdentityDto | string;

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
    FieldErrorComponent,
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

  protected readonly modeOptions = GAME_MODES.map((mode) => ({ label: `${mode}`, value: mode }));
  protected readonly tiles = TILES;
  protected readonly trainingLabel = TRAINING;
  protected readonly rules = GAME_RULES;
  protected readonly variantName = variantLabel;
  protected readonly checkoutModeOptions = [...CHECKOUT_MODES];
  protected readonly cricketScoringOptions = [...CRICKET_SCORINGS];
  protected readonly killerLivesOptions = KILLER_LIVES.map((lives) => ({ label: `${lives}`, value: lives }));
  protected readonly killerZoneOptions = [...KILLER_ZONES];
  protected readonly clockZoneOptions = [...CLOCK_ZONES];

  protected readonly signedIn = this.auth.isAuthenticated;
  /** One placeholder row per seat `restoreSeats` will open. */
  protected readonly skeletonSeats = [0];
  /** Rendered height of a seat's input and buttons, so the placeholders take the same space. */
  protected readonly seatRowHeight = '2.4375rem';
  /** Whether the session is known yet. The seats depend on it, so they are only
   * rendered once it is — otherwise they fill with the wrong default and
   * visibly change under the user. */
  protected readonly sessionResolved = signal(false);
  protected readonly suggestions = signal<PlayerIdentityDto[]>([]);
  protected readonly seatMessages = { required: $localize`:@@game.new.nameRequired:Bitte einen Namen eingeben.` };
  protected readonly formMessages = {
    killerSeats: $localize`:@@game.new.killerSeats:Killer braucht mindestens zwei Spieler.`,
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
    players: this.fb.array<FormControl<Seat>>([]),
  }, { validators: killerSeats });

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
  /** The game picked in the first step, kept in the URL so the back button returns to the tiles. */
  protected readonly chosen = toSignal(
    this.route.queryParamMap.pipe(map((params) => parseVariant(params.get('game')))),
    { initialValue: parseVariant(this.route.snapshot.queryParamMap.get('game')) },
  );
  private readonly heading = viewChild<ElementRef<HTMLElement>>('heading');
  /** Whether the tiles led here, so changing the game can step back instead of adding history. */
  private pickedHere = false;

  /** The setup played most, offered for one tap: undefined while it loads, null for none. */
  protected readonly quickStart = signal<QuickStartDto | null | undefined>(null);
  /** The own address-book entry, named "Du" in the quick start. */
  private readonly selfId = signal<string | null>(null);
  protected readonly starting = signal(false);
  protected readonly quickTitle = computed(() => {
    const quick = this.quickStart();
    return quick ? setupTitle(quick) : '';
  });
  protected readonly quickPlayers = computed(() =>
    (this.quickStart()?.players ?? [])
      .map((seat) => (seat.playerId !== null && seat.playerId === this.selfId() ? $localize`:@@player.list.self:Du` : seat.name))
      .join(', '),
  );
  protected readonly quickLabel = computed(
    () => $localize`:@@game.new.quickStartLabel:Schnellstart: ${this.quickTitle()}:setup: mit ${this.quickPlayers()}:players:`,
  );

  protected readonly rulesOpen = signal(false);
  protected readonly rulesVariant = signal<GameVariant>('x01');
  private readonly clockZone = toSignal(this.form.controls.clockZone.valueChanges, {
    initialValue: this.form.controls.clockZone.value,
  });
  /** Skipping ahead needs singles to tell apart from doubles and triples. */
  protected readonly clockSkippable = computed(() => this.clockZone() === 'any');

  constructor() {
    void this.restoreSeats();

    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      const variant = parseVariant(params.get('game'));
      if (variant !== null && variant !== this.form.controls.variant.value) {
        this.form.controls.variant.setValue(variant);
        this.form.controls.variant.markAsDirty();
      }
    });

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
    const { mode, variant, checkoutMode, players, cricketScoring, killerLives, killerZone, clockZone, clockSkip } =
      this.form.getRawValue();
    const seats = (players as Seat[]).map<PlayerSlotDto>((seat) =>
      typeof seat === 'string' ? { name: seat.trim() } : { playerId: seat.id },
    );
    this.create({
      mode,
      variant,
      checkoutMode,
      cricket: { scoring: cricketScoring },
      killer: { lives: killerLives, zone: killerZone },
      aroundTheClock: { zone: clockZone, skip: clockZone === 'any' && clockSkip },
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
          void this.router.navigate(['/game']);
        },
      });
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
      this.form.patchValue(settingsOf(previous));
      if (this.chosen() === null) {
        void this.showStep(previous.variant, true);
      }
      // Worst finish throws first, the winner last.
      const ranks = standings(previous, (value) => `${value}`).map((standing) => standing.rank);
      const order = previous.players
        .map((player, seat) => ({ player, rank: ranks[seat] }))
        .sort((a, b) => a.rank - b.rank)
        .map(({ player }) => player);
      const seats = await Promise.all(order.map((player) => this.reseat(player)));
      for (const seat of seats) {
        this.seats.push(this.fb.nonNullable.control<Seat>(seat, Validators.required));
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

      this.seats.push(self ? this.fb.nonNullable.control<Seat>(self) : this.createSeat(1));
    }
    this.sessionResolved.set(true);
  }

  /** The identity behind a previous seat: this account's address-book entry if
   * it has one, otherwise the seat itself, which the server accepts for a rematch. */
  private async reseat(player: PlayerDto): Promise<Seat> {
    const found = this.signedIn() ? await this.players.search(player.name) : [];
    return (
      found.find((identity) => identity.id === player.identityId) ?? {
        id: player.identityId,
        name: player.name,
        isSelf: false,
        linked: false,
      }
    );
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

const GROUP = $localize`:@@game.category.group:Gruppe`;
const TRAINING = $localize`:@@game.category.training:Training`;

/** A game on the first step's tiles; group and training games say so above their name. */
interface Tile {
  variant: GameVariant;
  kind?: string;
}

const TILES: readonly Tile[] = [
  { variant: 'x01' },
  { variant: 'cricket' },
  { variant: 'killer', kind: GROUP },
  { variant: 'elimination', kind: GROUP },
  { variant: 'around_the_clock', kind: TRAINING },
];

function parseVariant(value: string | null): GameVariant | null {
  return GAME_VARIANTS.find((option) => option.value === value)?.value ?? null;
}

/** A setup in one line: the game, then the settings that differ from its defaults. */
function setupTitle(quick: QuickStartDto): string {
  const checkout = optionLabel(CHECKOUT_MODES, quick.checkoutMode);
  switch (quick.variant) {
    case 'x01':
      return `${quick.mode} ${checkout}`;
    case 'elimination':
      return `Elimination ${quick.mode} ${checkout}`;
    case 'cricket': {
      const scoring = quick.cricket?.scoring ?? 'standard';
      return scoring === 'standard' ? 'Cricket' : `Cricket ${scoringLabel(scoring)}`;
    }
    case 'killer': {
      const lives = $localize`:@@game.detail.lives:${quick.killer?.lives ?? 3}:count: Leben`;
      const zone = quick.killer?.zone ?? 'double';
      return zone === 'double' ? `Killer ${lives}` : `Killer ${lives}, ${optionLabel(KILLER_ZONES, zone)}`;
    }
    case 'around_the_clock': {
      const zone = quick.aroundTheClock?.zone ?? 'any';
      const parts = ['Around the Clock'];
      if (zone !== 'any') {
        parts.push(optionLabel(CLOCK_ZONES, zone));
      }
      if (quick.aroundTheClock?.skip) {
        parts.push($localize`:@@game.detail.skip:mit Springen`);
      }
      return parts.join(' ');
    }
  }
}

/** Killer needs someone to knock out. */
function killerSeats(form: AbstractControl): ValidationErrors | null {
  const variant = form.get('variant')?.value as GameVariant | undefined;
  const seats = (form.get('players') as FormArray | null)?.length ?? 0;
  return variant === 'killer' && seats < 2 ? { killerSeats: true } : null;
}

/** The settings of a finished game, for its rematch; what it did not use stays as is. */
function settingsOf(game: GameStateDto) {
  return {
    variant: game.variant,
    ...(game.mode !== null && { mode: game.mode }),
    ...(game.checkoutMode !== null && { checkoutMode: game.checkoutMode }),
    ...(game.cricket !== null && { cricketScoring: game.cricket.scoring }),
    ...(game.killer !== null && { killerLives: game.killer.lives, killerZone: game.killer.zone }),
    ...(game.aroundTheClock !== null && {
      clockZone: game.aroundTheClock.zone,
      clockSkip: game.aroundTheClock.skip,
    }),
  };
}
