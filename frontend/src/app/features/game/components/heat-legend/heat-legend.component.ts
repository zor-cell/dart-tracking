import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** Points along the gradient, as fractions of the highest value. */
const STOPS = [0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 1];

/** A heatmap's fill scale from nothing to its highest value; the content labels the top end. */
@Component({
  selector: 'app-heat-legend',
  templateUrl: './heat-legend.component.html',
  styleUrl: './heat-legend.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { 'aria-hidden': 'true' },
})
export class HeatLegendComponent {
  /** CSS colour for a share of the highest value. */
  readonly color = input.required<(share: number) => string>();

  protected readonly gradient = computed(() => {
    const color = this.color();
    const stops = STOPS.map((share) => `${color(share)} ${share * 100}%`);
    return `linear-gradient(to right, transparent 0%, ${stops.join(', ')})`;
  });
}
