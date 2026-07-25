import {
  ChangeDetectionStrategy,
  Component,
  effect,
  ElementRef,
  input,
  OnDestroy,
  viewChild,
} from '@angular/core';

const DEFAULT_LINE_COLOR = 'rgba(255, 214, 10, 0.9)';
const LINE_WIDTH = 1.5;

/**
 * Draws normalized polylines over the camera preview. Used for the detected
 * board (so the user can check the calibration — the lines should sit on the
 * real rings and sector wires) and, in a different colour, the located dart.
 *
 * Expects to be positioned over a video rendered with `object-fit: cover`, and
 * reproduces that mapping — cover scales the frame to fill the box and crops
 * the overflow, so drawing straight onto the box would misalign the lines by
 * however much was cropped.
 */
@Component({
  selector: 'app-overlay',
  templateUrl: './overlay.component.html',
  styleUrl: './overlay.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OverlayComponent implements OnDestroy {
  /** Polylines of [x, y] points, normalized to 0..1 of the video frame. */
  readonly polylines = input.required<number[][][] | null>();

  /** The video being drawn over; supplies the frame's intrinsic size. */
  readonly video = input.required<HTMLVideoElement>();

  /** Stroke colour; defaults to the board's yellow. */
  readonly color = input(DEFAULT_LINE_COLOR);

  private readonly canvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  private readonly resizeObserver = new ResizeObserver(() => this.draw());

  constructor() {
    effect(() => {
      // Touch the inputs so the effect re-runs when any of them changes.
      this.polylines();
      this.video();
      this.color();
      this.draw();
    });

    effect(() => {
      this.resizeObserver.disconnect();
      this.resizeObserver.observe(this.canvasRef().nativeElement);
    });
  }

  ngOnDestroy(): void {
    this.resizeObserver.disconnect();
  }

  private draw(): void {
    const canvas = this.canvasRef().nativeElement;
    const context = canvas.getContext('2d');
    if (!context) {
      return;
    }

    // Back the canvas at device resolution so the lines are not blurry.
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);

    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);

    const polylines = this.polylines();
    const video = this.video();
    if (!polylines || !video.videoWidth || !video.videoHeight) {
      return;
    }

    // Replicate object-fit: cover — scale to fill, centre, and let the
    // overflow fall outside the box just as the video does.
    const scale = Math.max(width / video.videoWidth, height / video.videoHeight);
    const offsetX = (width - video.videoWidth * scale) / 2;
    const offsetY = (height - video.videoHeight * scale) / 2;

    context.strokeStyle = this.color();
    context.lineWidth = LINE_WIDTH;
    context.lineJoin = 'round';

    for (const line of polylines) {
      context.beginPath();
      line.forEach(([x, y], index) => {
        const pixelX = x * video.videoWidth * scale + offsetX;
        const pixelY = y * video.videoHeight * scale + offsetY;
        if (index === 0) {
          context.moveTo(pixelX, pixelY);
        } else {
          context.lineTo(pixelX, pixelY);
        }
      });
      context.stroke();
    }
  }
}
