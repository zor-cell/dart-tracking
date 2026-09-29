export type TriggerMoment = 'arm' | 'peak' | 'capture';

/** The trigger's own view of one frame of the episode, at diff resolution. */
export interface TriggerSnapshotDto {
  readonly moment: TriggerMoment;
  readonly tMs: number; // relative to the capturing frame, negative before it
  readonly width: number;
  readonly height: number;
  readonly luma: string; // base64, one byte per pixel, row-major
  readonly changed: string; // base64, one bit per pixel, row-major, most significant bit first
}
