/** Server -> camera: send a fresh frame to confirm the calibration still fits. */
export interface BoardCheckRequestedDto {
  readonly type: 'board_check_requested';
}
