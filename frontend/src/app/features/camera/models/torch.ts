/** The camera light. Not in the DOM typings: `torch` is an extension to the
 * media-track capabilities (docs/feature/done/kamera.md §2). */
interface TorchCapabilities extends MediaTrackCapabilities {
  readonly torch?: boolean;
}

interface TorchConstraint extends MediaTrackConstraintSet {
  readonly torch?: boolean;
}

/** Whether this track's camera has a light the browser will switch. */
export function hasTorch(track: MediaStreamTrack): boolean {
  const capabilities: TorchCapabilities = track.getCapabilities?.() ?? {};
  return capabilities.torch === true;
}

/** Switch the camera light; whether it took. */
export async function applyTorch(track: MediaStreamTrack, on: boolean): Promise<boolean> {
  try {
    await track.applyConstraints({ advanced: [{ torch: on } as TorchConstraint] });
    return true;
  } catch {
    return false;
  }
}
