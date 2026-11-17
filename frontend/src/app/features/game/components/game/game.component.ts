import {
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  effect,
  ElementRef,
  inject,
  LOCALE_ID,
  OnDestroy,
  OnInit,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DOCUMENT, formatNumber } from '@angular/common';
import { CdkDrag, CdkDragDrop, CdkDropList } from '@angular/cdk/drag-drop';
import {Router, RouterLink} from '@angular/router';
import {Button} from 'primeng/button';
import {ProgressSpinner} from 'primeng/progressspinner';
import {Skeleton} from 'primeng/skeleton';
import {AuthService} from '../../../auth/services/auth.service';
import {OverlayComponent} from '../../../calibration/components/overlay/overlay.component';
import {CalibrationService} from '../../../calibration/services/calibration.service';
import {DetectionService} from '../../../detection/services/detection.service';
import {FrameDiffService} from '../../../detection/services/frame-diff.service';
import {DartDto} from '../../dto/dart.dto';
import {GameStateDto} from '../../dto/game-state.dto';
import {ScoreboardEntry} from '../../models/scoreboard-entry';
import {standings} from '../../models/variant-standing';
import {fieldLabel, zoneLabel} from '../../models/variant-options';
import {finishOf, playOf} from '../../models/game-settings';
import {DARTS_PER_TURN} from '../../models/visit';
import {GameService} from '../../services/game.service';
import {GameSessionService} from '../../services/game-session.service';
import {GameDraftService} from '../../services/game-draft.service';
import {ScreenWakeLockService} from '../../services/screen-wake-lock.service';
import {GameTopBarComponent} from '../game-top-bar/game-top-bar.component';
import {TrackingToggleComponent} from '../tracking-toggle/tracking-toggle.component';
import {ScoreboardComponent} from '../scoreboard/scoreboard.component';
import {VirtualBoardComponent} from '../virtual-board/virtual-board.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { backState } from '../../../../core/view/models/back-state';
import { HoldPressDirective } from '../../../../core/view/directives/hold-press.directive';
import { RepeatPressDirective } from '../../../../core/view/directives/repeat-press.directive';
import { ConfirmService } from '../../../../core/view/services/confirm.service';
import { CorrectionPendingDto } from '../../dto/correction-pending.dto';
import { TurnDto } from '../../dto/turn.dto';
import { VisitMark } from '../../models/visit-mark';
import { readStored, writeStored } from '../../../../core/storage/models/browser-storage';

/** A side-column key: a fixed field, booked as it stands whatever D or T is set to. */
type FixedKey = {
  readonly label: string;
  readonly value: number;
  readonly multiplier: number;
};

/** One suggestion box: its label, and whether it resets an opponent or only sets
 * up the next visit rather than winning the leg. `leave` marks a setup's last dart,
 * `reset` the reset route's dart under a finish. */
type CheckoutSlot = {
  readonly label: string | null;
  readonly eliminating: boolean;
  readonly reset: string | null;
  readonly setup: boolean;
  readonly leave: number | null;
  readonly shadow: boolean;
};

/** Fields to suggest in the empty slots; `hostile` when they take an opponent's life. */
type TargetRoute = { readonly darts: readonly string[]; readonly hostile: boolean };

/** An empty box after the darts of an earlier visit. */
const EMPTY_SLOT: CheckoutSlot = {
  label: null,
  eliminating: false,
  reset: null,
  setup: false,
  leave: null,
  shadow: false,
};

const MISS: FixedKey ={ label: '0', value: 0, multiplier: 0 };
const BULL: FixedKey = { label: '25', value: 25, multiplier: 1 };
const BULLSEYE: FixedKey = { label: '50', value: 25, multiplier: 2 };

/** Score keypad layout: four numbers per row. */
const PAD_ROWS: readonly number[][] = [
  [1, 2, 3, 4],
  [5, 6, 7, 8],
  [9, 10, 11, 12],
  [13, 14, 15, 16],
  [17, 18, 19, 20],
];

/** Whether this camera device shows the drawn board while it films. */
const BOARD_SHOWN_KEY = 'dart-tracking.boardShown';

/** When the camera picture is laid out again after its size changed, in ms. */
const RELAYOUT_DELAYS: readonly number[] = [0, 300, 1200];

/** The side column beside the number rows, top to bottom. */
const SIDE_KEYS: readonly FixedKey[] = [MISS, BULL, BULLSEYE];

@Component({
  selector: 'app-game',
  imports: [
    RouterLink,
    ScoreboardComponent,
    Button,
    ProgressSpinner,
    Skeleton,
    OverlayComponent,
    VirtualBoardComponent,
    GameTopBarComponent,
    TrackingToggleComponent,
    EmptyStateComponent,
    LoadingStateComponent,
    CdkDropList,
    CdkDrag,
    RepeatPressDirective,
    HoldPressDirective,
  ],
  templateUrl: './game.component.html',
  styleUrl: './game.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class.camera-expanded]': "expanded() === 'camera'",
    '[class.board-expanded]': "expanded() === 'board'",
  },
})
export class GameComponent implements OnInit, OnDestroy {
  protected readonly game = inject(GameService);

  private readonly session = inject(GameSessionService);
  private readonly calibration = inject(CalibrationService);
  private readonly throwCapture = inject(FrameDiffService);
  private readonly detection = inject(DetectionService);
  private readonly wakeLock = inject(ScreenWakeLockService);
  private readonly document = inject(DOCUMENT);
  private readonly locale = inject(LOCALE_ID);

  // Optional: these live behind the "game active" gate, so they are absent until
  // the state is (re)loaded — which after a full reload is a few ticks after init.
  private readonly videoRef = viewChild<ElementRef<HTMLVideoElement>>('video');
  private readonly diffCanvasRef = viewChild<ElementRef<HTMLCanvasElement>>('diffCanvas');
  private readonly captureCanvasRef = viewChild<ElementRef<HTMLCanvasElement>>('captureCanvas');

  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly drafts = inject(GameDraftService);
  private readonly confirm = inject(ConfirmService);
  protected readonly signedIn = this.auth.isAuthenticated;
  /** The game detail leads back here, so a rematch is one tap away. */
  protected readonly returnState = backState($localize`:@@common.nav.game:Spiel`);
  protected readonly calibrateLabel = $localize`:@@game.calibrate:Board kalibrieren`;
  protected readonly recalibrateLabel = $localize`:@@game.recalibrate:Rekalibrieren`;
  protected readonly fullscreenLabel = $localize`:@@game.fullscreen:Kamera im Vollbild`;
  protected readonly boardFullscreenLabel = $localize`:@@game.boardFullscreen:Board im Vollbild`;
  protected readonly exitFullscreenLabel = $localize`:@@game.exitFullscreen:Vollbild verlassen`;
  protected readonly backLabel = $localize`:@@game.previousVisit:Runde davor anzeigen`;
  protected readonly forwardLabel = $localize`:@@game.nextVisit:Nächste Runde anzeigen`;
  protected readonly deleteDartLabel = $localize`:@@game.deleteDart:Ausgewählten Dart löschen`;
  protected readonly pickLabel = (label: string): string =>
    $localize`:@@game.pickDart:${label}:field: auswählen und korrigieren`;
  protected readonly shadowLabel = (label: string | null): string =>
    $localize`:@@game.shadowDart:${label}:field:, erkannt, nicht gewertet`;
  protected readonly deviceRole = this.session.role;
  protected readonly cameraPhase = this.session.phase;
  protected readonly cameraError = this.session.cameraError;
  protected readonly calibrationStatus = this.calibration.status;
  protected readonly calibrationOverlay = this.calibration.overlay;
  protected readonly roomCalibration = this.calibration.roomState;
  protected readonly calibrationFailure = this.calibration.failureMessage;
  protected readonly roomCalibrationFailure = this.calibration.roomFailureMessage;
  protected readonly roundDarts = this.detection.roundDarts;
  protected readonly detectionStatusLabel = this.throwCapture.statusLabel;
  protected readonly detectionFeedback = this.detection.feedbackLabel;

  protected readonly padRows = PAD_ROWS;
  protected readonly sideKeys = SIDE_KEYS;

  /** Which of camera and board fills the screen below the top bar, if either. */
  protected readonly expanded = signal<'camera' | 'board' | null>(null);

  /** Whether this camera device shows the drawn board, its picture shrunk to an inset. */
  protected readonly boardShown = signal(false);
  /** The stream's width over its height, which the inset takes on. */
  protected readonly videoAspect = signal(4 / 3);

  /** Whether the game is still being fetched, true only with a persisted id. */
  protected readonly restoring = signal(this.game.peekGameId() !== null);

  /** The setup left half done that the view hands over to, while there is no game. */
  protected readonly keptSetup = computed(() =>
    this.restoring() || this.game.state() !== null
      ? null
      : this.drafts.read(this.auth.user()?.id ?? null),
  );

  /** Rematch and done: small text in a taller button. */
  protected readonly finishButtonTokens = { root: { sm: { paddingY: '0.625rem' } } };

  /** Placeholder rows while the state is on its way. */
  protected readonly skeletonDarts = [0, 1, 2];

  /** Reads as the handover for a normal visit and as the win for the last one. */
  protected readonly confirmLabel = computed(() =>
    this.game.winPending()
      ? $localize`:@@game.confirmWin:Sieg bestätigen`
      : this.endsByHold()
        ? $localize`:@@game.confirmVisitOrEnd:Runde bestätigen — gedrückt halten beendet das Training`
        : $localize`:@@game.confirmVisit:Runde bestätigen — nächster Spieler`,
  );

  protected readonly multiplier = signal<1 | 2 | 3>(1);
  protected readonly multiplierPrefix = computed(() =>
    this.multiplier() === 2 ? 'D' : this.multiplier() === 3 ? 'T' : '',
  );

  // The visit browsed back to, from 0; null shows the open one.
  private readonly browsedTurn = signal<number | null>(null);

  /** The earlier visit on show, or null while the open one is; a visit the game dropped falls back. */
  protected readonly viewedTurn = computed(() => {
    const browsed = this.browsedTurn();
    const turns = this.game.state()?.turns.length ?? 0;
    return browsed !== null && browsed < turns - 1 ? browsed : null;
  });

  /** Index of the visit on show: the browsed one, else the open one. */
  private readonly shownIndex = computed(
    () => this.viewedTurn() ?? (this.game.state()?.turns.length ?? 1) - 1,
  );

  /** The visit the dart row and the board show. */
  protected readonly shownTurn = computed<TurnDto | null>(
    () => this.game.state()?.turns[this.shownIndex()] ?? null,
  );

  /** The browsed visit's thrower and round, which the scoreboard marks. */
  protected readonly visitMark = computed<VisitMark | null>(() => {
    const state = this.game.state();
    const viewed = this.viewedTurn();
    if (state === null || viewed === null) {
      return null;
    }
    const playerId = state.turns[viewed].playerId;
    return {
      seat: state.players.findIndex((player) => player.id === playerId),
      round: roundOf(state.turns, viewed),
    };
  });

  // The picked dart together with the visit it was picked in.
  private readonly pickedDart = signal<{ turn: number; index: number } | null>(null);

  /** The dart a keypad tap corrects instead of appending, or null to append; only
   * a dart of the visit on show. */
  protected readonly selectedDart = computed(() => {
    const picked = this.pickedDart();
    const darts = this.shownTurn()?.darts.length ?? 0;
    return picked !== null && picked.turn === this.shownIndex() && picked.index < darts
      ? picked.index
      : null;
  });

  /** Whether the keypad books at all: appending needs the open visit with room in
   * it, correcting a selected dart does not. */
  protected readonly padAccepts = computed(
    () =>
      this.selectedDart() !== null || (this.viewedTurn() === null && this.game.acceptsManualDarts()),
  );

  /** The keypad takes the finish block's place while a finished game gets corrected. */
  protected readonly padShown = computed(() => !this.game.finished() || this.selectedDart() !== null);

  /** A running free training ends by holding the confirm key. */
  protected readonly endsByHold = computed(
    () => this.game.state()?.settings.variant === 'training' && !this.game.finished(),
  );

  /** The visit on show, drawn on the virtual board. */
  protected readonly currentDarts = computed<readonly DartDto[]>(
    () => this.shownTurn()?.darts ?? [],
  );

  protected readonly scoreboardEntries = computed<ScoreboardEntry[]>(() => {
    const state = this.game.state();
    if (state === null) {
      return [];
    }
    const seats = standings(state, (value, digits) => formatNumber(value, this.locale, digits));
    const finished = (id: number) => state.finisherIds.includes(id);
    // A training ends for everyone at once, with nobody winning it.
    const trainingDone = state.ended && (state.settings.variant === 'training' || state.settings.variant === 'personal');
    const out = (id: number) => finished(id) || state.places.includes(id) || state.waitingIds.includes(id);
    const running = state.players.filter((player) => !out(player.id));
    const ranks = running.map((player) => seats[state.players.indexOf(player)].rank);
    const best = Math.max(...ranks);
    const alone = ranks.filter((rank) => rank === best).length === 1;
    const open = state.winnerId === null && !state.ended && running.length > 1;
    return state.players.map((player, seat) => ({
      ...seats[seat],
      id: player.id,
      name: player.name,
      leading: open && alone && running.includes(player) && seats[seat].rank === best,
      reset: player.justReset,
      eliminations: state.settings.variant === 'elimination' ? player.eliminations : null,
      finished: finished(player.id) || trainingDone,
      waiting: state.waitingIds.includes(player.id),
      place: finishOf(state.settings).playOn && state.places.includes(player.id) ? state.places.indexOf(player.id) + 1 : null,
    }));
  });

  /** The fields the variant has the thrower aim at next, without a checkout to suggest. */
  private readonly targetRoute = computed<TargetRoute | null>(() => {
    const state = this.game.state();
    if (state === null || state.winnerId !== null || state.ended) {
      return null;
    }
    return targetRoute(state);
  });

  /**
   * The slots after the darts already thrown, with the suggested route: a winning
   * finish over a reset or setup route, shadow darts in the first free slots.
   */
  protected readonly checkoutSlots = computed<readonly CheckoutSlot[]>(() => {
    if (this.viewedTurn() !== null) {
      const thrown = this.shownTurn()?.darts.length ?? DARTS_PER_TURN;
      return Array.from({ length: DARTS_PER_TURN - thrown }, () => EMPTY_SLOT);
    }
    const thrown = this.game.currentTurn()?.darts.length ?? 0;
    const state = this.game.state();
    const checkout = state?.checkout ?? null;
    const elimination = state?.elimination ?? null;
    const setup = checkout === null ? (state?.setup ?? null) : null;
    const target = this.targetRoute();
    const route = checkout ?? setup?.darts ?? elimination ?? target?.darts ?? null;
    const eliminating =
      checkout === null && setup === null && (elimination !== null || target?.hostile === true);
    const shadows = this.game.shadowDarts();
    return Array.from({ length: DARTS_PER_TURN - thrown }, (_, index) => {
      const shadow = shadows[index];
      const last = setup !== null && index === setup.darts.length - 1;
      return shadow
        ? { label: shadow.label, eliminating: false, reset: null, setup: false, leave: null, shadow: true }
        : {
            label: route?.[index] ?? null,
            eliminating,
            reset: checkout !== null ? (elimination?.[index] ?? null) : null,
            setup: setup !== null && index < setup.darts.length,
            leave: last ? setup.leave : null,
            shadow: false,
          };
    });
  });

  constructor() {

    // Without a game, a setup left half done is where the game tab leads.
    effect(() => {
      const draft = this.keptSetup();
      if (draft !== null) {
        const queryParams = { game: draft.chosen };
        void this.router.navigate(['/game/new'], { queryParams, replaceUrl: true });
      }
    });

    // The picture stays large until the board is calibrated, then the view of last time returns.
    let tracking = false;
    effect(() => {
      const phase = this.cameraPhase();
      if (phase === 'idle') {
        this.collapse();
        this.boardShown.set(false);
      } else if (phase === 'tracking' && !tracking && readStored(BOARD_SHOWN_KEY) === 'true') {
        this.boardShown.set(true);
      }
      tracking = phase === 'tracking';
    });

    // Leaving browser fullscreen by gesture or back button collapses the view too.
    const onFullscreenChange = () => {
      if (!this.document.fullscreenElement) {
        this.expanded.set(null);
      }
    };
    this.document.addEventListener('fullscreenchange', onFullscreenChange);

    // A dart booked into the open visit brings the view back to it, unless a
    // correction is under way.
    let open: string | null = null;
    effect(() => {
      const turns = this.game.state()?.turns;
      const now = turns === undefined ? null : `${turns.length}:${turns.at(-1)?.darts.length}`;
      if (open !== null && now !== open && untracked(() => this.selectedDart()) === null) {
        this.browsedTurn.set(null);
      }
      open = now;
    });

    // A correction in an earlier visit that changes more than that visit asks first.
    this.game.pendingCorrections
      .pipe(takeUntilDestroyed())
      .subscribe((pending) => this.askCorrection(pending));

    // A picked dart is a mode, so anything outside the two blocks that act on
    // it — the dart row and the keypad — leaves that mode.
    const onDocumentPointerDown = (event: Event) => {
      const target = event.target as HTMLElement | null;
      if (!target?.closest('.turn__darts, .turn__undo, .scorepad')) {
        this.pickedDart.set(null);
      }
    };
    this.document.addEventListener('pointerdown', onDocumentPointerDown);

    inject(DestroyRef).onDestroy(() => {
      this.document.removeEventListener('fullscreenchange', onFullscreenChange);
      this.document.removeEventListener('pointerdown', onDocumentPointerDown);
    });

    // Hand the session this view's camera elements once they exist, so it resumes
    // the session or the phase from before.
    effect(() => {
      const video = this.videoRef()?.nativeElement;
      const diffCanvas = this.diffCanvasRef()?.nativeElement;
      const captureCanvas = this.captureCanvasRef()?.nativeElement;
      if (video && diffCanvas && captureCanvas) {
        this.session.attachView(video, diffCanvas, captureCanvas);
      }
    });
  }

  ngOnInit(): void {
    this.wakeLock.hold();
    // Refetch the game after a full reload so the view — and with it the camera
    // elements — can render; wiring and camera resume then happen on attach.
    void this.session.restore().finally(() => this.restoring.set(false));
  }

  /** Leave the finished game on this device; the view stays, offering a new game. */
  protected leaveGame(): void {
    this.session.leave();
  }

  protected startCamera(): Promise<void> {
    return this.session.startCamera();
  }

  /** WebKit keeps painting the stream at its old size once the frame size changes;
   * narrowing the element briefly, now and again later, lays the picture out anew. */
  protected relayoutVideo(video: HTMLVideoElement): void {
    if (video.videoWidth && video.videoHeight) {
      this.videoAspect.set(video.videoWidth / video.videoHeight);
    }
    for (const delay of RELAYOUT_DELAYS) {
      setTimeout(() => {
        video.style.width = 'calc(100% - 1px)';
        requestAnimationFrame(() => requestAnimationFrame(() => (video.style.width = '')));
      }, delay);
    }
  }

  /** Fills the screen with the camera or the board below the top bar; browser
   * fullscreen where supported, a fixed overlay otherwise (iPhone). */
  protected toggleExpanded(view: 'camera' | 'board'): void {
    if (this.expanded() === view) {
      this.collapse();
      return;
    }
    this.expanded.set(view);
    this.document.documentElement.requestFullscreen?.().catch(() => {});
  }

  /** The board in the picture's place, while the camera keeps tracking in an inset. */
  protected showBoard(): void {
    if (this.expanded() === 'camera') {
      this.expanded.set('board');
    } else {
      this.collapse();
    }
    this.boardShown.set(true);
    writeStored(BOARD_SHOWN_KEY, 'true');
  }

  /** The camera picture large again, in the board's place. */
  protected showCamera(): void {
    if (this.expanded() === 'board') {
      this.expanded.set('camera');
    }
    this.boardShown.set(false);
    writeStored(BOARD_SHOWN_KEY, null);
  }

  protected switchRole(): void {
    this.collapse();
    this.boardShown.set(false);
    this.session.setRole(this.deviceRole() === 'camera' ? 'scoreboard' : 'camera');
  }

  protected calibrateBoard(): Promise<void> {
    return this.session.calibrate();
  }

  /** Scoreboard counterpart to `calibrateBoard`: this device has no picture, so
   * it asks the game's cameras to take one. */
  protected requestCalibration(): void {
    this.calibration.requestCalibration();
  }

  /** End the visit — or, on the dart that finishes the game, take the win. The
   * server has no handover left to apply once someone is out. */
  protected confirmTurn(): void {
    if (!this.game.currentTurn()?.darts.length) {
      return;
    }
    if (this.game.winner() !== null) {
      this.game.confirmWin();
    } else {
      this.game.nextPlayer();
    }
  }

  /** Pick a thrown dart out for correction, or drop the pick by tapping it
   * again. Nothing is booked or taken back here — the next keypad tap decides
   * which it was. */
  protected selectDart(index: number): void {
    const turn = this.shownIndex();
    this.pickedDart.update((picked) =>
      picked?.turn === turn && picked.index === index ? null : { turn, index },
    );
  }

  /** Show the visit before the one on show. */
  protected browseBack(): void {
    this.pickedDart.set(null);
    this.browsedTurn.set(Math.max(this.shownIndex() - 1, 0));
  }

  /** Show the visit after the one on show, up to the open one. */
  protected browseForward(): void {
    const viewed = this.viewedTurn();
    if (viewed !== null) {
      this.pickedDart.set(null);
      this.browsedTurn.set(viewed + 1);
    }
  }

  /** Take the picked dart out: from the open visit, or as a miss from an earlier one. */
  protected deleteDart(): void {
    const selected = this.selectedDart();
    if (selected !== null) {
      this.game.removeDart(selected, this.viewedTurn() ?? undefined);
      this.pickedDart.set(null);
    }
  }

  /** End the free training for the whole room. */
  protected endTraining(): void {
    this.game.setEnded(true);
  }

  /** Drop a dragged dart in its new place. The order comes back from the server
   * like every other change, so nothing is reordered here. */
  protected dropDart(event: CdkDragDrop<unknown>): void {
    this.pickedDart.set(null);
    if (event.previousIndex === event.currentIndex) {
      return;
    }
    this.game.moveDart(event.previousIndex, event.currentIndex, this.viewedTurn() ?? undefined);
  }

  /** A 1–20 key: booked with the active multiplier, which then falls back to
   * single — the multiplier applies to one dart, not to the rest of the visit. */
  protected enterNumber(value: number): void {
    this.book(value, this.multiplier());
  }

  /** A miss/bull key: booked as its own fixed field. */
  protected enterFixed(key: FixedKey): void {
    this.book(key.value, key.multiplier);
  }

  /** One keypad tap: the picked dart's new field, or the next dart of the visit.
   * The pick is spent either way, so the tap after it appends again. */
  private book(value: number, multiplier: number): void {
    const selected = this.selectedDart();
    if (selected === null) {
      this.game.registerDart(value, multiplier);
    } else {
      this.game.replaceDart(selected, value, multiplier, this.viewedTurn() ?? undefined);
      this.pickedDart.set(null);
    }
    this.multiplier.set(1);
  }

  private collapse(): void {
    this.expanded.set(null);
    if (this.document.fullscreenElement) {
      void this.document.exitFullscreen();
    }
  }

  /** Ask before a correction that ends the game earlier or puts players out earlier. */
  private askCorrection(pending: CorrectionPendingDto): void {
    const state = this.game.state();
    if (state === null) {
      return;
    }
    const name = (id: number | null) => state.players.find((player) => player.id === id)?.name ?? '';
    const accept = () => this.game.confirmCorrection(pending);
    if (pending.wonAt !== null) {
      const round = roundOf(state.turns, pending.wonAt);
      const winner = name(pending.winnerId);
      const dropped = pending.dropped;
      this.confirm.ask(
        $localize`:@@game.earlyWin.title:Sieg in Runde ${round}:round:?`,
        dropped === 1
          ? $localize`:@@game.earlyWin.one:Damit hat ${winner}:name: in Runde ${round}:round: gewonnen. Die Runde danach fällt weg.`
          : $localize`:@@game.earlyWin.other:Damit hat ${winner}:name: in Runde ${round}:round: gewonnen. Die ${dropped}:count: Runden danach fallen weg.`,
        dropped === 1
          ? $localize`:@@game.earlyWin.dropOne:Runde verwerfen`
          : $localize`:@@game.earlyWin.dropOther:Runden verwerfen`,
        accept,
      );
      return;
    }
    const names = pending.outIds.map(name).join(', ');
    this.confirm.ask(
      $localize`:@@game.earlyOut.title:Früher draußen?`,
      $localize`:@@game.earlyOut.message:Damit ist ${names}:names: früher draußen. Die Runden danach zählen nicht.`,
      $localize`:@@game.earlyOut.accept:Korrigieren`,
      accept,
    );
  }

  protected toggleDouble(): void {
    this.multiplier.update((current) => (current === 2 ? 1 : 2));
  }

  protected toggleTriple(): void {
    this.multiplier.update((current) => (current === 3 ? 1 : 3));
  }

  ngOnDestroy(): void {
    // Leaving the game screen only pauses the loop; the session (camera + socket)
    // keeps running so returning is instant. Teardown is leave() alone.
    this.session.detachView();
    this.wakeLock.release();
  }
}

/** Around the Clock: the next targets in turn. Killer: the own field until it makes a
 * killer, then the strongest opponent's. Training: the field to hit, in every slot. */
function targetRoute(state: GameStateDto): TargetRoute | null {
  const seat = state.currentPlayerIndex;
  const play = playOf(state);
  const training = play.variant === 'training' ? play.standing.players[seat] : null;
  if (training?.target) {
    const field = fieldLabel(training.target);
    const darts = Math.min(training.left, state.dartsRemaining);
    return { darts: Array.from({ length: darts }, () => field), hostile: false };
  }
  if (play.variant === 'personal') {
    const ahead = play.standing.players[seat].ahead.slice(0, state.dartsRemaining);
    return { darts: ahead.map(fieldLabel), hostile: false };
  }
  if (play.variant === 'around_the_clock') {
    const zone = play.settings.zone;
    const target = play.standing.players[seat].target;
    if (target === null) {
      return null;
    }
    const ahead = [...Array.from({ length: 20 }, (_, index) => index + 1), 25].filter((n) =>
      target === 25 ? n === 25 : n >= target,
    );
    return { darts: ahead.slice(0, state.dartsRemaining).map((n) => zoneLabel(n, zone)), hostile: false };
  }
  if (play.variant !== 'killer') {
    return null;
  }
  const killer = play.standing;
  const zone = play.settings.zone;
  const own = killer.players[seat];
  if (!own.killer) {
    return { darts: [zoneLabel(own.number, zone)], hostile: false };
  }
  const count = killer.players.length;
  const victim = killer.players
    .map((player, index) => ({ player, after: (index - seat + count) % count }))
    .filter(({ player, after }) => after !== 0 && player.lives > 0)
    .sort(
      (a, b) =>
        b.player.lives - a.player.lives ||
        Number(b.player.killer) - Number(a.player.killer) ||
        b.player.kills - a.player.kills ||
        a.after - b.after,
    )[0]?.player;
  if (victim === undefined) {
    return null;
  }
  const field = zoneLabel(victim.number, zone);
  return { darts: Array.from({ length: state.dartsRemaining }, () => field), hostile: true };
}

/** The visit's number among its thrower's visits, from 1. */
function roundOf(turns: readonly TurnDto[], index: number): number {
  const playerId = turns[index].playerId;
  return turns.slice(0, index + 1).filter((turn) => turn.playerId === playerId).length;
}
