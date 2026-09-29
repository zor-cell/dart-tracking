import type { ThrowDetectorState } from '../models/throw-detector';

/** One processed frame of the trigger, as recorded for the episode that fired a capture. */
export interface TriggerSampleDto {
  readonly tMs: number; // time relative to the capture, negative before it
  readonly state: ThrowDetectorState;
  readonly activeBlocks: number;
  readonly ambientBlocks: number;
  readonly cells: readonly number[]; // indices of the active cells, row-major
}
