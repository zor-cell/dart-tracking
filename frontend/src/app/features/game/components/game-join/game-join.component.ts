import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { ProgressSpinner } from 'primeng/progressspinner';
import { GameService } from '../../services/game.service';

/**
 * Landing point of a shared game link (`/game/join/:gameId`), the screen a
 * second device sees after scanning the QR code from the share dialog.
 *
 * It only resolves the id and steps aside: on success the game becomes this
 * device's active one and the game view takes over. The camera is not started —
 * a device that joins is keeping score, and it may still pick up the camera role
 * itself from the game view.
 */
@Component({
  selector: 'app-game-join',
  imports: [Button, ProgressSpinner, RouterLink],
  templateUrl: './game-join.component.html',
  styleUrl: './game-join.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameJoinComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly game = inject(GameService);

  // Only the failure is rendered; a success navigates away, so there is no
  // "joined" state to show.
  protected readonly failed = signal(false);

  async ngOnInit(): Promise<void> {
    const gameId = this.route.snapshot.paramMap.get('gameId');
    if (gameId && (await this.game.join(gameId))) {
      await this.router.navigate(['/game'], { replaceUrl: true });
      return;
    }
    this.failed.set(true);
  }
}
