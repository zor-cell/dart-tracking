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
import { GameService } from '../../services/game.service';
import {NotificationService} from "../../../../core/services/notification.service";

@Component({
  selector: 'app-game-setup',
  imports: [ReactiveFormsModule, Button, InputText, SelectButton],
  templateUrl: './game-setup.component.html',
  styleUrl: './game-setup.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameSetupComponent {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly game = inject(GameService);
  private readonly notification = inject(NotificationService);

  protected readonly modeOptions = GAME_MODES.map((mode) => ({ label: `${mode}`, value: mode }));

  protected readonly form = this.fb.group({
    mode: this.fb.nonNullable.control<GameMode>(501, Validators.required),
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
    const { mode, players } = this.form.getRawValue();
    this.game.createGame({ mode, playerNames: players }).subscribe(() => {
      this.notification.showSuccess("Spiel erstellt");
      this.router.navigate(['/game']);
    });
  }

  private createPlayer(name: string): FormControl<string> {
    return this.fb.nonNullable.control(name, Validators.required);
  }
}
