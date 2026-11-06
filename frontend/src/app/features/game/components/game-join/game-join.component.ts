import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { GameService } from '../../services/game.service';
import { GameSessionService } from '../../services/game-session.service';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';

/**
 * Landing point of a shared game link (`/game/join/:gameId`): resolves the id and
 * enters the game without a camera, which the game view can switch on.
 */
@Component({
  selector: 'app-game-join',
  imports: [Button, LoadingStateComponent, EmptyStateComponent, RouterLink],
  templateUrl: './game-join.component.html',
  styleUrl: './game-join.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameJoinComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly game = inject(GameService);
  private readonly session = inject(GameSessionService);

  protected readonly failed = signal(false);

  async ngOnInit(): Promise<void> {
    const gameId = this.route.snapshot.paramMap.get('gameId');
    if (gameId === null || !(await this.game.load(gameId))) {
      this.failed.set(true);
      return;
    }
    this.game.connect();
    this.session.setRole('scoreboard');
    await this.router.navigate(['/game'], { replaceUrl: true });
  }
}
