import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormArray, FormBuilder, FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AutoComplete, AutoCompleteCompleteEvent } from 'primeng/autocomplete';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { SelectButton } from 'primeng/selectbutton';
import { Skeleton } from 'primeng/skeleton';
import { AuthService } from '../../../auth/services/auth.service';
import { PlayerIdentityDto } from '../../../player/dto/player-identity.dto';
import { PlayerService } from '../../../player/services/player.service';
import { SettingsService } from '../../../settings/services/settings.service';
import { GAME_MODES, GameMode } from '../../models/game-mode';
import { CHECKOUT_MODES, CheckoutMode } from '../../models/checkout-mode';
import { PlayerSlotDto } from '../../dto/player-slot.dto';
import { GameService } from '../../services/game.service';
import { GameSessionService } from '../../services/game-session.service';

/** What a seat holds: a known identity, or the name typed for a guest. */
type Seat = PlayerIdentityDto | string;

@Component({
  selector: 'app-game-setup',
  imports: [ReactiveFormsModule, AutoComplete, Button, InputText, SelectButton, Skeleton],
  templateUrl: './game-new.component.html',
  styleUrl: './game-new.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameNewComponent {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly game = inject(GameService);
  private readonly session = inject(GameSessionService);
  private readonly auth = inject(AuthService);
  private readonly players = inject(PlayerService);
  private readonly settings = inject(SettingsService);

  protected readonly modeOptions = GAME_MODES.map((mode) => ({ label: `${mode}`, value: mode }));
  protected readonly checkoutModeOptions = [...CHECKOUT_MODES];

  protected readonly signedIn = this.auth.isAuthenticated;
  /** One placeholder row per seat `restoreSeats` will open. */
  protected readonly skeletonSeats = [0, 1];
  /** Rendered height of a seat's input and buttons, so the placeholders take the same space. */
  protected readonly seatRowHeight = '2.4375rem';
  /** Whether the session is known yet. The seats depend on it, so they are only
   * rendered once it is — otherwise they fill with the wrong default and
   * visibly change under the user. */
  protected readonly sessionResolved = signal(false);
  protected readonly suggestions = signal<PlayerIdentityDto[]>([]);

  protected readonly form = this.fb.group({
    mode: this.fb.nonNullable.control<GameMode>(501, Validators.required),
    checkoutMode: this.fb.nonNullable.control<CheckoutMode>('double_out', Validators.required),
    players: this.fb.array<FormControl<Seat>>([]),
  });

  constructor() {
    void this.restoreSeats();
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
    const { mode, checkoutMode, players } = this.form.getRawValue();
    const seats = (players as Seat[]).map<PlayerSlotDto>((seat) =>
      typeof seat === 'string' ? { name: seat.trim() } : { playerId: seat.id },
    );

    this.game
      .createGame({
        mode,
        checkoutMode,
        players: seats,
        evaluationEnabled: this.settings.evaluationEnabled(),
      })
      .subscribe(() => {
        this.session.setRole('camera');
        this.router.navigate(['/game']);
      });
  }

  /** Seat the account itself first — the one player who is always there. */
  private async restoreSeats(): Promise<void> {
    await this.auth.ready;

    const self = this.signedIn()
      ? (await this.players.search('')).find((identity) => identity.isSelf)
      : undefined;

    this.seats.push(self ? this.fb.nonNullable.control<Seat>(self) : this.createSeat(1));
    this.seats.push(this.createSeat(2));
    this.sessionResolved.set(true);
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
