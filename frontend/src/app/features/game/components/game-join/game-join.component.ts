import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { ProgressSpinner } from 'primeng/progressspinner';
import { DeviceRole } from '../../models/device-role';
import { GameService } from '../../services/game.service';
import { GameSessionService } from '../../services/game-session.service';

/** Resolving the link, then the choice of what this device will do, or a dead link. */
type JoinStatus = 'resolving' | 'choosing' | 'failed';

/**
 * Landing point of a shared game link (`/game/join/:gameId`), the screen a
 * second device sees after scanning the QR code from the share dialog.
 *
 * It resolves the id, then asks the one question the link cannot answer: does
 * this device film the board, or does it only follow the game? That is a
 * property of where the phone is about to be put down, so it is asked here
 * rather than encoded in the link — and it stays changeable in the game view.
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
  private readonly session = inject(GameSessionService);

  protected readonly status = signal<JoinStatus>('resolving');

  protected readonly cameraJoinAvailable = false;

  /** Mode and players of the resolved game — the check that this is the right one. */
  protected readonly summary = computed(() => {
    const state = this.game.state();
    return state ? `${state.mode} — ${state.players.map((player) => player.name).join(', ')}` : '';
  });

  async ngOnInit(): Promise<void> {
    const gameId = this.route.snapshot.paramMap.get('gameId');
    const joined = gameId !== null && (await this.game.join(gameId));
    this.status.set(joined ? 'choosing' : 'failed');
  }

  /** Take the picked role into the game view; starting the camera stays an
   * explicit tap there, so the permission prompt is not sprung on arrival. */
  protected async enter(role: DeviceRole): Promise<void> {
    this.session.setRole(role);
    await this.router.navigate(['/game'], { replaceUrl: true });
  }
}
