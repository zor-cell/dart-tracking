/** Client -> server: hold the camera's bookings for the whole room, or resume them. */
export interface SetTrackingPausedDto {
  readonly type: 'set_tracking_paused';
  readonly paused: boolean;
}
