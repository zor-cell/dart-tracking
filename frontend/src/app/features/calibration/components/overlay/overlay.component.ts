import {
  ChangeDetectionStrategy,
  Component,
  effect,
  ElementRef,
  input,
  OnDestroy,
  viewChild,
} from '@angular/core';
import { containRect } from '../../../camera/models/video-fit';

const DEFAULT_LINE_COLOR = '#ffffff';
const LINE_WIDTH = 1;
const LABEL_FONT = '600 12px system-ui, sans-serif';
// Matches the marker outline on the virtual board.
const OUTLINE_COLOR = '#1b1b1b';
const OUTLINE_EXTRA_WIDTH = 2;
const LABEL_OUTLINE_WIDTH = 2;

/**
 * Draws normalized polylines over the camera preview. Used for the detected
 * board (so the user can check the calibration — the lines should sit on the
 * real rings and sector wires) and, in a different colour, the located dart.
 *
 * Expects to sit over a video rendered with `object-fit: contain`.
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

  /** Stroke colour; defaults to the board's white. */
  readonly color = input(DEFAULT_LINE_COLOR);

  /** Stroke width in CSS pixels. */
  readonly lineWidth = input(LINE_WIDTH);

  /** Text drawn beside the first point of the first polyline, e.g. the dart's ordinal. */
  readonly label = input<string | null>(null);

  /** Whether lines and label get a dark outline. */
  readonly outlined = input(false);

  private readonly canvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  private readonly resizeObserver = new ResizeObserver(() => this.draw());

  constructor() {
    effect(() => {
      // Touch the inputs so the effect re-runs when any of them changes.
      this.polylines();
      this.video();
      this.color();
      this.lineWidth();
      this.label();
      this.outlined();
      this.draw();
    });

    effect(() => {
      this.resizeObserver.disconnect();
      this.resizeObserver.observe(this.canvasRef().nativeElement);
    });

    // `video.videoWidth`/`videoHeight` drive the contain mapping but are not
    // reactive: when the polylines arrive before the stream has reported its
    // intrinsic size, the first draw finds 0x0, no-ops, and nothing re-runs it —
    // so the outline stays blank until the next calibration happens to redraw it.
    // Redraw when the video reports or changes its dimensions, so it appears as
    // soon as it can be mapped.
    effect((onCleanup) => {
      const video = this.video();
      const redraw = () => this.draw();
      video.addEventListener('loadedmetadata', redraw);
      video.addEventListener('resize', redraw);
      onCleanup(() => {
        video.removeEventListener('loadedmetadata', redraw);
        video.removeEventListener('resize', redraw);
      });
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

    const frame = containRect(width, height, video.videoWidth, video.videoHeight);

    const toPixel = ([x, y]: number[]): [number, number] => [
      frame.x + x * frame.width,
      frame.y + y * frame.height,
    ];

    context.lineJoin = 'round';
    context.lineCap = 'round';
    if (this.outlined()) {
      this.strokeLines(context, polylines, toPixel, OUTLINE_COLOR, this.lineWidth() + OUTLINE_EXTRA_WIDTH);
    }
    this.strokeLines(context, polylines, toPixel, this.color(), this.lineWidth());

    const label = this.label();
    const anchor = polylines[0]?.[0];
    if (label && anchor) {
      const [pixelX, pixelY] = toPixel(anchor);
      context.font = LABEL_FONT;
      context.textBaseline = 'middle';
      if (this.outlined()) {
        context.strokeStyle = OUTLINE_COLOR;
        context.lineWidth = LABEL_OUTLINE_WIDTH;
        context.strokeText(label, pixelX + 10, pixelY - 10);
      }
      context.fillStyle = this.color();
      context.fillText(label, pixelX + 10, pixelY - 10);
    }
  }

  private strokeLines(
    context: CanvasRenderingContext2D,
    polylines: number[][][],
    toPixel: (point: number[]) => [number, number],
    color: string,
    width: number,
  ): void {
    context.strokeStyle = color;
    context.lineWidth = width;
    for (const line of polylines) {
      context.beginPath();
      line.forEach((point, index) => {
        const [pixelX, pixelY] = toPixel(point);
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
