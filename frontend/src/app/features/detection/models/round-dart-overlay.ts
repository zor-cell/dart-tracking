import { DartDto } from '../../game/dto/dart.dto';
import { CORRECTED_DART_COLOR, dartColor, SHADOW_DART_COLOR } from '../../game/models/dart-colors';

/** One located dart to draw: its polylines, its place in the visit, and the
 * colour for that place. */
export interface RoundDartOverlay {
  readonly polylines: number[][][];
  readonly dartIndex: number;
  readonly color: string;
  /** The tip this outline was drawn at, in board millimetres — what it is
   * matched back to the visit by. Null until the state holding it has arrived. */
  readonly tip: readonly [number, number] | null;
  /** Booked as another field by hand; the outline stays, greyed out, for the rest of the visit. */
  readonly corrected: boolean;
}

/** A freshly located dart at `dartIndex` of a visit with `booked` booked darts. */
export function locatedDart(
  polylines: number[][][],
  dartIndex: number,
  booked: number,
): RoundDartOverlay {
  return { polylines, dartIndex, color: colorFor(dartIndex, booked), tip: null, corrected: false };
}

/** Where an outline belongs in the visit as it now stands — booked darts, then
 * shadow darts — greyed out once its dart was booked by hand, or nothing when it is gone. */
export function placeOverlay(
  overlay: RoundDartOverlay,
  darts: readonly DartDto[],
  booked: number,
  previousCount: number,
): RoundDartOverlay[] {
  if (overlay.corrected) {
    return [overlay];
  }
  const tip = overlay.tip ?? darts[overlay.dartIndex]?.position ?? null;
  const dartIndex =
    tip === null ? overlay.dartIndex : darts.findIndex((d) => sameTip(d.position, tip));
  if (dartIndex >= 0 && dartIndex < darts.length) {
    return [{ ...overlay, tip, dartIndex, color: colorFor(dartIndex, booked) }];
  }
  const replaced = darts.length >= previousCount && darts[overlay.dartIndex]?.position === null;
  return replaced && tip !== null
    ? [{ ...overlay, tip, corrected: true, color: CORRECTED_DART_COLOR }]
    : [];
}

function colorFor(dartIndex: number, booked: number): string {
  return dartIndex < booked ? dartColor(dartIndex) : SHADOW_DART_COLOR;
}

function sameTip(a: readonly [number, number] | null, b: readonly [number, number]): boolean {
  return a !== null && a[0] === b[0] && a[1] === b[1];
}
