import {
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  effect,
  ElementRef,
  inject,
  OnDestroy,
  OnInit,
  signal,
  viewChild,
} from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { CdkDrag, CdkDragDrop, CdkDropList } from '@angular/cdk/drag-drop';
import {Router, RouterLink} from '@angular/router';
import {Button} from 'primeng/button';
import {ProgressSpinner} from 'primeng/progressspinner';
import {Skeleton} from 'primeng/skeleton';
import {OverlayComponent} from '../../../calibration/components/overlay/overlay.component';
import {CalibrationService} from '../../../calibration/services/calibration.service';
import {DetectionService} from '../../../detection/services/detection.service';
import {FrameDiffService} from '../../../detection/services/frame-diff.service';
import {SettingsService} from '../../../settings/services/settings.service';
import {DartDto} from '../../dto/dart.dto';
import {PlayerDto} from '../../dto/player.dto';
import {DARTS_PER_TURN} from '../../models/visit';
import {GameService} from '../../services/game.service';
import {GameSessionService} from '../../services/game-session.service';
import {ScreenWakeLockService} from '../../services/screen-wake-lock.service';
import {GameTopBarComponent} from '../game-top-bar/game-top-bar.component';
import {VirtualBoardComponent} from '../virtual-board/virtual-board.component';

/** A side-column key: a fixed field, booked as it stands whatever D or T is set to. */
type FixedKey = {
  readonly label: string;
  readonly value: number;
  readonly multiplier: number;
};

/** One suggestion box: its label, and whether it resets an opponent rather than
 * winning the leg. */
type CheckoutSlot = {
  readonly label: string | null;
  readonly eliminating: boolean;
  readonly shadow: boolean;
};

const MISS: FixedKey = { label: '0', value: 0, multiplier: 0 };
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

/** The side column beside the number rows, top to bottom. */
const SIDE_KEYS: readonly FixedKey[] = [MISS, BULL, BULLSEYE];

@Component({
  selector: 'app-game',
  imports: [
    RouterLink,
    Button,
    ProgressSpinner,
    Skeleton,
    OverlayComponent,
    VirtualBoardComponent,
    GameTopBarComponent,
    CdkDropList,
    CdkDrag,
  ],
  templateUrl: './game.component.html',
  styleUrl: './game.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameComponent implements OnInit, OnDestroy {
  protected readonly game = inject(GameService);
  protected readonly settings = inject(SettingsService);

  private readonly session = inject(GameSessionService);
  private readonly calibration = inject(CalibrationService);
  private readonly throwCapture = inject(FrameDiffService);
  private readonly detection = inject(DetectionService);
  private readonly wakeLock = inject(ScreenWakeLockService);
  private readonly document = inject(DOCUMENT);
  private readonly router = inject(Router);

  // Optional: these live behind the "game active" gate, so they are absent until
  // the state is (re)loaded — which after a full reload is a few ticks after init.
  private readonly cameraRef = viewChild<ElementRef<HTMLDivElement>>('camera');
  private readonly videoRef = viewChild<ElementRef<HTMLVideoElement>>('video');
  private readonly diffCanvasRef = viewChild<ElementRef<HTMLCanvasElement>>('diffCanvas');
  private readonly captureCanvasRef = viewChild<ElementRef<HTMLCanvasElement>>('captureCanvas');
  private readonly detectionDebugCanvasRef = viewChild<ElementRef<HTMLCanvasElement>>('detectionDebugCanvas');
  private readonly scoreboardRef = viewChild<ElementRef<HTMLUListElement>>('scoreboard');

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
  protected readonly detectionDebug = this.throwCapture.debug;
  protected readonly detectionEvents = this.detection.events;

  // The client debug view (change mask, numbers, event log, sent-frame preview)
  // is on only while tracking and switched on — separate from the server-side
  // detection-image dump (settings.debugDetection).
  protected readonly debugActive = computed(
    () => this.settings.debugClientDetection() && this.cameraPhase() === 'tracking',
  );

  protected readonly padRows = PAD_ROWS;
  protected readonly sideKeys = SIDE_KEYS;

  /** The stream's aspect ratio as CSS, so the preview shows the whole frame. */
  protected readonly videoAspect = signal('4 / 3');
  protected readonly cameraExpanded = signal(false);

  /** Whether the game is still being fetched — the placeholder below the view is
   * for "no game", which is a different answer from "not yet known". Without a
   * persisted id there is nothing to fetch, so the answer is known at once. */
  protected readonly restoring = signal(this.game.peekGameId() !== null);

  /** Rematch and done: small text in a taller button. */
  protected readonly finishButtonTokens = { root: { sm: { paddingY: '0.625rem' } } };

  /** Placeholder rows while the state is on its way: two, the smallest game. */
  protected readonly skeletonPlayers = [0, 1];
  protected readonly skeletonDarts = [0, 1, 2];

  /** Reads as the handover for a normal visit and as the win for the last one. */
  protected readonly confirmLabel = computed(() =>
    this.game.winPending() ? 'Sieg bestätigen' : 'Runde bestätigen — nächster Spieler',
  );

  protected readonly multiplier = signal<1 | 2 | 3>(1);
  protected readonly multiplierPrefix = computed(() =>
    this.multiplier() === 2 ? 'D' : this.multiplier() === 3 ? 'T' : '',
  );

  // The picked dart together with the visit it was picked in.
  private readonly pickedDart = signal<{ turn: number; index: number } | null>(null);

  /** The dart a keypad tap corrects instead of appending, or null to append.
   * Read back against the open visit, so a pick cannot outlive it and reattach
   * to whatever stands in that place in the next one. */
  protected readonly selectedDart = computed(() => {
    const picked = this.pickedDart();
    const turns = this.game.state()?.turns;
    if (picked === null || turns === undefined) {
      return null;
    }
    const open = turns.length - 1;
    return picked.turn === open && picked.index < (turns[open]?.darts.length ?? 0)
      ? picked.index
      : null;
  });

  /** Whether the keypad books at all: appending needs room in the visit,
   * correcting a selected dart does not. */
  protected readonly padAccepts = computed(
    () => this.game.acceptsManualDarts() || this.selectedDart() !== null,
  );

  /** The visit being thrown, drawn on the virtual board as it fills up. */
  protected readonly currentDarts = computed<readonly DartDto[]>(
    () => this.game.currentTurn()?.darts ?? [],
  );

  /**
   * How many player cards share the row's width. Up to three, so the thrower
   * keeps a neighbour on each side; beyond that the row scrolls.
   */
  protected readonly visiblePlayers = computed(() =>
    Math.min(this.game.state()?.players.length ?? 1, 3),
  );

  /**
   * The slots after the darts already thrown, carrying the suggested route where
   * there is one. Sized off the darts thrown rather than `dartsRemaining`: a
   * busted visit has none remaining, which would drop the boxes from the row.
   * A winning finish outranks a reset, so the elimination route only fills the
   * slots when there is no checkout. Shadow darts take the first free slots.
   */
  protected readonly checkoutSlots = computed<readonly CheckoutSlot[]>(() => {
    const thrown = this.game.currentTurn()?.darts.length ?? 0;
    const state = this.game.state();
    const checkout = state?.checkout ?? null;
    const elimination = state?.elimination ?? null;
    const route = checkout ?? elimination;
    const eliminating = checkout === null && elimination !== null;
    const shadows = this.game.shadowDarts();
    return Array.from({ length: DARTS_PER_TURN - thrown }, (_, index) => {
      const shadow = shadows[index];
      return shadow
        ? { label: shadow.label, eliminating: false, shadow: true }
        : { label: route?.[index] ?? null, eliminating, shadow: false };
    });
  });

  /** The number on a player's card: points still needed in x01, points gathered
   * so far in elimination — the same value read from opposite ends. */
  protected score(player: PlayerDto): number {
    const state = this.game.state();
    if (state === null || state.variant !== 'elimination') {
      return player.remaining;
    }
    return state.mode - player.remaining;
  }

  constructor() {
    // Follow play along the row, so the thrower stays in the middle and the two
    // around them stay in view. A no-op while everyone fits.
    effect(() => {
      const index = this.game.state()?.currentPlayerIndex;
      const list = this.scoreboardRef()?.nativeElement;
      if (list === undefined || index === undefined) {
        return;
      }
      const card = list.children.item(index) as HTMLElement | null;
      if (card !== null) {
        list.scrollTo({ left: card.offsetLeft + card.offsetWidth / 2 - list.clientWidth / 2 });
      }
    });

    // Attach the change-mask canvas whenever the debug panel is on screen, and
    // detach it the moment it leaves — keeping the loop's debug work off unless
    // someone is watching.
    effect(() => {
      const canvas = this.detectionDebugCanvasRef()?.nativeElement ?? null;
      this.throwCapture.setDebugCanvas(this.settings.debugClientDetection() ? canvas : null);
    });

    effect((onCleanup) => {
      const video = this.videoRef()?.nativeElement;
      if (!video) {
        return;
      }
      const update = () => {
        if (video.videoWidth && video.videoHeight) {
          this.videoAspect.set(`${video.videoWidth} / ${video.videoHeight}`);
        }
      };
      update();
      video.addEventListener('loadedmetadata', update);
      video.addEventListener('resize', update);
      onCleanup(() => {
        video.removeEventListener('loadedmetadata', update);
        video.removeEventListener('resize', update);
      });
    });

    effect(() => {
      if (this.cameraPhase() === 'idle') {
        this.collapseCamera();
      }
    });

    // Leaving browser fullscreen by gesture or back button collapses the view too.
    const onFullscreenChange = () => {
      if (!this.document.fullscreenElement) {
        this.cameraExpanded.set(false);
      }
    };
    this.document.addEventListener('fullscreenchange', onFullscreenChange);

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

    // Hand the session this view's camera elements once they exist. They live
    // behind the "game active" gate, so after a full reload — where the state is
    // refetched first — they appear a few ticks after init, not at view init.
    // The session then resumes an ongoing session or the phase from before.
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
    const persisted = this.restoring();
    void this.session
      .restore()
      .then((restored) => {
        // A stored game that is over leads back to the start screen.
        if (persisted && !restored) {
          void this.router.navigate(['/start'], { replaceUrl: true });
        }
      })
      .finally(() => this.restoring.set(false));
  }

  /** Leave the finished game on this device and return to the start screen. */
  protected leaveGame(): void {
    this.session.leave();
    void this.router.navigate(['/start']);
  }

  protected startCamera(): Promise<void> {
    return this.session.startCamera();
  }

  /** Fills the screen with the camera; browser fullscreen where supported, a
   * fixed overlay otherwise (iPhone). */
  protected toggleCameraExpanded(): void {
    if (this.cameraExpanded()) {
      this.collapseCamera();
      return;
    }
    this.cameraExpanded.set(true);
    this.cameraRef()?.nativeElement.requestFullscreen?.().catch(() => {});
  }

  protected switchRole(): void {
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
    const turn = this.openTurnIndex();
    this.pickedDart.update((picked) =>
      picked?.turn === turn && picked.index === index ? null : { turn, index },
    );
  }

  /** The back key's other job: with a dart picked out there is no step back to
   * take — that dart is not the last one — so it takes that dart instead,
   * which is how a phantom booking in the middle of a visit goes. */
  protected undoOrDelete(): void {
    const selected = this.selectedDart();
    if (selected === null) {
      this.game.undo();
      return;
    }
    this.game.removeDart(selected);
    this.pickedDart.set(null);
  }

  /** Drop a dragged dart in its new place. The order comes back from the server
   * like every other change, so nothing is reordered here. */
  protected dropDart(event: CdkDragDrop<unknown>): void {
    this.pickedDart.set(null);
    if (event.previousIndex === event.currentIndex) {
      return;
    }
    this.game.moveDart(event.previousIndex, event.currentIndex);
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
      this.game.replaceDart(selected, value, multiplier);
      this.pickedDart.set(null);
    }
    this.multiplier.set(1);
  }

  private collapseCamera(): void {
    this.cameraExpanded.set(false);
    if (this.document.fullscreenElement) {
      void this.document.exitFullscreen();
    }
  }

  private openTurnIndex(): number {
    return (this.game.state()?.turns.length ?? 1) - 1;
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
