/** Server -> announcer: the board calibration just failed, or holds again after a failure. */
export interface CalibrationAnnouncementDto {
  readonly type: 'calibration_announcement';
  readonly calibrated: boolean;
}
