/** Client -> server: a still frame of the empty board to check the calibration against. */
export interface BoardCheckFrameDto {
  readonly type: 'board_check_frame';
  readonly image: string; // base64-encoded JPEG
}
