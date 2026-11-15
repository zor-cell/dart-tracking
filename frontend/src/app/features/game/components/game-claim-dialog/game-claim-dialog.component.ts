import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  model,
  output,
  signal,
} from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Button } from 'primeng/button';
import { Dialog } from 'primeng/dialog';
import { Message } from 'primeng/message';
import { RadioButton } from 'primeng/radiobutton';
import { HttpErrorResponse } from '@angular/common/http';
import { GameSummaryDto } from '../../dto/game-summary.dto';
import { gameTitle } from '../../models/game-settings';
import { GameClaimService } from '../../services/game-claim.service';
import { SHORT_DATE_TIME } from '../../../../core/i18n/models/date-format';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { DIALOG_STYLE } from '../../../../core/view/models/dialog-style';

/** The seat picked for the account, or `none` when it only kept score. */
type SeatPick = number | 'none';

/** Walks through the anonymous games of this device, taking each over or leaving it. */
@Component({
  selector: 'app-game-claim-dialog',
  imports: [Button, DatePipe, Dialog, Message, RadioButton, ReactiveFormsModule],
  templateUrl: './game-claim-dialog.component.html',
  styleUrl: './game-claim-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameClaimDialogComponent {
  private readonly claims = inject(GameClaimService);

  readonly games = input.required<readonly GameSummaryDto[]>();
  readonly visible = model(false);
  /** After the last game was taken over or left. */
  readonly done = output<void>();

  protected readonly dialogStyle = DIALOG_STYLE;
  protected readonly shortDateTime = SHORT_DATE_TIME;
  protected readonly form = new FormGroup({
    seat: new FormControl<SeatPick | null>(null, Validators.required),
  });
  protected readonly index = signal(0);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly current = computed(() => this.games()[this.index()] ?? null);
  protected readonly progress = computed(() => {
    const total = this.games().length;
    const number = this.index() + 1;
    return total > 1 ? $localize`:@@game.claim.progress:Spiel ${number}:number: von ${total}:total:` : '';
  });

  constructor() {
    effect(() => {
      this.games();
      this.index.set(0);
    });
  }

  protected title(game: GameSummaryDto): string {
    return gameTitle(game.settings);
  }

  protected async submit(game: GameSummaryDto): Promise<void> {
    const seat = this.form.controls.seat.value;
    if (seat === null || this.busy()) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.claims.claim(game.id, seat === 'none' ? null : seat);
      this.next();
    } catch (failure) {
      if (failure instanceof HttpErrorResponse && failure.status === 404) {
        this.next();
      } else {
        this.error.set(
          httpErrorMessage(
            failure,
            { 422: $localize`:@@game.claim.seatTaken:Dieser Platz gehört schon einem Konto.` },
            $localize`:@@game.claim.failed:Das Spiel konnte nicht übernommen werden.`,
          ),
        );
      }
    } finally {
      this.busy.set(false);
    }
  }

  protected skip(game: GameSummaryDto): void {
    this.claims.forget(game.id);
    this.next();
  }

  private next(): void {
    this.form.reset();
    this.error.set(null);
    if (this.index() + 1 < this.games().length) {
      this.index.update((index) => index + 1);
    } else {
      this.visible.set(false);
      this.done.emit();
    }
  }
}
