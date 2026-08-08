import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import {
  FormArray,
  FormBuilder,
  FormControl,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { Router } from '@angular/router';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { SelectButton } from 'primeng/selectbutton';
import { GAME_MODES, GameMode } from '../../models/game-mode';
import { CHECKOUT_MODES, CheckoutMode } from '../../models/checkout-mode';
import { GameService } from '../../services/game.service';
import { GameSessionService } from '../../services/game-session.service';
import {NotificationService} from "../../../../core/notification/services/notification.service";

@Component({
  selector: 'app-game-setup',
  imports: [ReactiveFormsModule, Button, InputText, SelectButton],
  templateUrl: './game-new.component.html',
  styleUrl: './game-new.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameNewComponent {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly game = inject(GameService);
  private readonly session = inject(GameSessionService);
  private readonly notification = inject(NotificationService);

  protected readonly modeOptions = GAME_MODES.map((mode) => ({ label: `${mode}`, value: mode }));
  protected readonly checkoutModeOptions = [...CHECKOUT_MODES];

  protected readonly form = this.fb.group({
    mode: this.fb.nonNullable.control<GameMode>(501, Validators.required),
    checkoutMode: this.fb.nonNullable.control<CheckoutMode>('double_out', Validators.required),
    players: this.fb.array([this.createPlayer('Spieler 1'), this.createPlayer('Spieler 2')]),
  });

  protected get players(): FormArray<FormControl<string>> {
    return this.form.controls.players;
  }

  protected addPlayer(): void {
    this.players.push(this.createPlayer(`Spieler ${this.players.length + 1}`));
  }

  protected removePlayer(index: number): void {
    if (this.players.length > 1) {
      this.players.removeAt(index);
    }
  }

  protected startGame(): void {
    if (this.form.invalid) {
      return;
    }
    const { mode, checkoutMode, players } = this.form.getRawValue();
    // Whoever sets up the game is the one standing at the board, so this device
    // films it. It also has to be set explicitly: the role only changes on the
    // way into a game, and this device may have joined the last one as a
    // scoreboard.
    this.session.setRole('camera');
    this.game.createGame({ mode, checkoutMode, playerNames: players }).subscribe(() => {
      this.router.navigate(['/game']);
    });
  }

  private createPlayer(name: string): FormControl<string> {
    return this.fb.nonNullable.control(name, Validators.required);
  }
}
