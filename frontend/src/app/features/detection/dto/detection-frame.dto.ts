import { ThrowTriggerDto } from './throw-trigger.dto';

/** Client -> server: a still frame captured after the frame-diff trigger. */
export interface DetectionFrameDto {
  readonly type: 'detection_frame';
  readonly image: string; // base64-encoded JPEG
  readonly debug?: boolean;
  readonly trigger?: ThrowTriggerDto;
}
