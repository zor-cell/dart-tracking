import { readStored, writeStored } from '../../../core/storage/models/browser-storage';

/** What a heatmap shows: where each tip landed, or the darts counted per field. */
export type HeatmapLayer = 'tips' | 'fields';

export const HEATMAP_LAYERS: readonly { label: string; value: HeatmapLayer }[] = [
  { label: 'Treffer', value: 'tips' },
  { label: 'Felder', value: 'fields' },
];

/** Where the last chosen layer is kept; every heatmap opens on it. */
const LAYER_KEY = 'dart-tracking.heatmapLayer';

export function storedHeatmapLayer(): HeatmapLayer {
  const stored = readStored(LAYER_KEY);
  return HEATMAP_LAYERS.find((layer) => layer.value === stored)?.value ?? 'tips';
}

export function storeHeatmapLayer(layer: HeatmapLayer): void {
  writeStored(LAYER_KEY, layer);
}
