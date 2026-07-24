/** Client -> server frame kinds; the payload is always a base64-encoded JPEG. */
export type OutgoingFrameType = 'calibration_frame' | 'detection_frame';
