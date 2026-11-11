import { ChangeDetectionStrategy, Component, computed, input, model } from '@angular/core';
import { Dialog } from 'primeng/dialog';
import { DIALOG_STYLE } from '../../../../core/view/models/dialog-style';
import { GAME_RULES } from '../../models/game-rules';
import { GameVariant, variantLabel } from '../../models/game-variant';

/** The rules of one variant, opened from the new-game view and from the running game. */
@Component({
  selector: 'app-game-rules',
  imports: [Dialog],
  templateUrl: './game-rules.component.html',
  styleUrl: './game-rules.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameRulesComponent {
  readonly variant = input.required<GameVariant>();
  readonly visible = model(false);

  protected readonly dialogStyle = DIALOG_STYLE;
  protected readonly title = computed(() => variantLabel(this.variant()));
  protected readonly rules = computed(() => GAME_RULES[this.variant()].rules);
}
