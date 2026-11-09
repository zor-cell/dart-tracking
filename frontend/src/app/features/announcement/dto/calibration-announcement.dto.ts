/** Server -> announcer: the board calibration just failed, or holds again after a failure,
 * with the clips that say so. */
export interface CalibrationAnnouncementDto {
  readonly type: 'calibration_announcement';
  readonly calibrated: boolean;
  readonly clips: readonly string[];
}
