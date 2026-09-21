import { CdkDrag, CdkDragDrop, CdkDragHandle, CdkDropList } from '@angular/cdk/drag-drop';
import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  Injector,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormArray, FormBuilder, FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AutoComplete, AutoCompleteCompleteEvent } from 'primeng/autocomplete';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { SelectButton } from 'primeng/selectbutton';
import { Skeleton } from 'primeng/skeleton';
import { SocketService } from '../../../../core/socket/services/socket.service';
import { AuthService } from '../../../auth/services/auth.service';
import { PlayerIdentityDto } from '../../../player/dto/player-identity.dto';
import { PlayerService } from '../../../player/services/player.service';
import { SettingsService } from '../../../settings/services/settings.service';
import { GAME_MODES, GameMode } from '../../models/game-mode';
import { CHECKOUT_MODES, CheckoutMode } from '../../models/checkout-mode';
import { GAME_VARIANTS, GameVariant } from '../../models/game-variant';
import { PlayerDto } from '../../dto/player.dto';
import { PlayerSlotDto } from '../../dto/player-slot.dto';
import { GameService } from '../../services/game.service';
import { GameSessionService } from '../../services/game-session.service';

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
    CdkDropList,
    CdkDrag,
    CdkDragHandle,
  ],
  templateUrl: './game-new.component.html',
  styleUrl: './game-new.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameNewComponent {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly injector = inject(Injector);
  private readonly game = inject(GameService);
  private readonly session = inject(GameSessionService);
  private readonly auth = inject(AuthService);
  private readonly players = inject(PlayerService);
  private readonly settings = inject(SettingsService);
  private readonly socket = inject(SocketService);

  protected readonly modeOptions = GAME_MODES.map((mode) => ({ label: `${mode}`, value: mode }));
  protected readonly variantOptions = [...GAME_VARIANTS];
  protected readonly checkoutModeOptions = [...CHECKOUT_MODES];

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

  protected readonly form = this.fb.group({
    mode: this.fb.nonNullable.control<GameMode>(501, Validators.required),
    variant: this.fb.nonNullable.control<GameVariant>('x01', Validators.required),
    checkoutMode: this.fb.nonNullable.control<CheckoutMode>('double_out', Validators.required),
    players: this.fb.array<FormControl<Seat>>([]),
  });

  /** The finished game being replayed, once `restoreSeats` has confirmed it exists. */
  private rematchId: string | null = null;

  private readonly variant = toSignal(this.form.controls.variant.valueChanges, {
    initialValue: this.form.controls.variant.value,
  });
  /** Elimination counts up, so the score field is a target rather than a mode. */
  protected readonly isElimination = computed(() => this.variant() === 'elimination');

  constructor() {
    void this.restoreSeats();

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

  protected dropSeat(event: CdkDragDrop<unknown>): void {
    this.moveSeat(event.previousIndex, event.currentIndex);
  }

  /** Keyboard counterpart to dragging: arrow keys on the grip move the seat by one. */
  protected stepSeat(event: Event, index: number, step: -1 | 1): void {
    event.preventDefault();
    const target = index + step;
    if (target < 0 || target >= this.seats.length) {
      return;
    }
    const grip = event.target as HTMLElement;
    this.moveSeat(index, target);
    afterNextRender(() => grip.focus(), { injector: this.injector });
  }

  protected label(seat: Seat): string {
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
    const { mode, variant, checkoutMode, players } = this.form.getRawValue();
    const seats = (players as Seat[]).map<PlayerSlotDto>((seat) =>
      typeof seat === 'string' ? { name: seat.trim() } : { playerId: seat.id },
    );
    const rematchOf = this.rematchId ?? undefined;

    this.game
      .createGame({
        mode,
        variant,
        checkoutMode,
        players: seats,
        evaluationEnabled: this.settings.evaluationEnabled(),
        rematchOf,
      })
      .subscribe(() => {
        // A rematch keeps every device's role; a fresh game starts on the camera.
        if (rematchOf === undefined) {
          this.session.setRole('camera');
        }
        this.router.navigate(['/game']);
      });
  }

  private moveSeat(from: number, to: number): void {
    if (from === to) {
      return;
    }
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
      this.form.patchValue({
        mode: previous.mode,
        variant: previous.variant,
        checkoutMode: previous.checkoutMode,
      });
      // Worst finish throws first: most points left leads, the winner goes last.
      const order = [...previous.players].sort((a, b) => b.remaining - a.remaining);
      const seats = await Promise.all(order.map((player) => this.reseat(player)));
      for (const seat of seats) {
        this.seats.push(this.fb.nonNullable.control<Seat>(seat, Validators.required));
      }
    } else {
      const self = this.signedIn()
        ? (await this.players.search('')).find((identity) => identity.isSelf)
        : undefined;

      this.seats.push(self ? this.fb.nonNullable.control<Seat>(self) : this.createSeat(1));
    }
    this.sessionResolved.set(true);
  }

  /** The identity behind a previous seat, if it is in this account's address
   * book; otherwise its name, taken as a guest. */
  private async reseat(player: PlayerDto): Promise<Seat> {
    if (!this.signedIn()) {
      return player.name;
    }
    const found = await this.players.search(player.name);
    return found.find((identity) => identity.id === player.identityId) ?? player.name;
  }

  /** Signed out there is no address book, so a placeholder name saves typing;
   * signed in an empty seat is the prompt to pick someone. */
  private createSeat(position: number): FormControl<Seat> {
    return this.fb.nonNullable.control<Seat>(
      this.signedIn() ? '' : `Spieler ${position}`,
      Validators.required,
    );
  }
}
