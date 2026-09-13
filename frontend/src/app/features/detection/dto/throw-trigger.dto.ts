/**
 * What the frame-diff episode that fired this capture looked like, sent along
 * with the frame so the server can log it next to its own blob metrics.
 */
export interface ThrowTriggerDto {
  readonly peakBlocks: number; // highest active-cell count in the episode
  readonly peakExcess: number; // highest count above the steady baseline
  // Bounding box of the active cells at the peak frame, in cells.
  readonly spanCols: number;
  readonly spanRows: number;
  readonly frames: number; // episode length, in processed frames
  readonly timedOut: boolean; // captured by the motion timeout instead of settling
  readonly gridCols: number; // grid the counts and spans are relative to
  readonly gridRows: number;
}
