/** Exposure and white balance controls. Not in the DOM typings: they are
 * extensions to the media-track capabilities and settings. */
interface ExposureCapabilities extends MediaTrackCapabilities {
  readonly exposureMode?: readonly string[];
  readonly whiteBalanceMode?: readonly string[];
}

interface ExposureSettings extends MediaTrackSettings {
  readonly exposureTime?: number;
  readonly colorTemperature?: number;
}

interface ExposureConstraint extends MediaTrackConstraintSet {
  exposureMode?: string;
  exposureTime?: number;
  whiteBalanceMode?: string;
  colorTemperature?: number;
}

/** Hold exposure and white balance at their current values, where the browser
 * lets it; whether anything was locked. */
export async function lockExposure(track: MediaStreamTrack): Promise<boolean> {
  const capabilities: ExposureCapabilities = track.getCapabilities?.() ?? {};
  const settings: ExposureSettings = track.getSettings();
  const constraint: ExposureConstraint = {};
  if (capabilities.exposureMode?.includes('manual')) {
    constraint.exposureMode = 'manual';
    if (settings.exposureTime !== undefined) {
      constraint.exposureTime = settings.exposureTime;
    }
  }
  if (capabilities.whiteBalanceMode?.includes('manual')) {
    constraint.whiteBalanceMode = 'manual';
    if (settings.colorTemperature !== undefined) {
      constraint.colorTemperature = settings.colorTemperature;
    }
  }
  return Object.keys(constraint).length > 0 && apply(track, constraint);
}

/** Hand exposure and white balance back to the camera's automatic. */
export async function unlockExposure(track: MediaStreamTrack): Promise<void> {
  const capabilities: ExposureCapabilities = track.getCapabilities?.() ?? {};
  const constraint: ExposureConstraint = {};
  if (capabilities.exposureMode?.includes('continuous')) {
    constraint.exposureMode = 'continuous';
  }
  if (capabilities.whiteBalanceMode?.includes('continuous')) {
    constraint.whiteBalanceMode = 'continuous';
  }
  if (Object.keys(constraint).length > 0) {
    await apply(track, constraint);
  }
}

async function apply(track: MediaStreamTrack, constraint: ExposureConstraint): Promise<boolean> {
  try {
    await track.applyConstraints({ advanced: [constraint] });
    return true;
  } catch {
    return false;
  }
}
