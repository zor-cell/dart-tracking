import { DartDto } from '../../game/dto/dart.dto';
import { CORRECTED_DART_COLOR, dartColor, SHADOW_DART_COLOR } from '../../game/models/dart-colors';
import { locatedDart, placeOverlay, RoundDartOverlay } from './round-dart-overlay';

const LINES = [[[0.1, 0.2]]];

function dart(label: string, position: [number, number] | null): DartDto {
  return { label, position };
}

function drawnAt(dartIndex: number, tip: [number, number]): RoundDartOverlay {
  return { ...locatedDart(LINES, dartIndex, 3), tip };
}

describe('placeOverlay', () => {
  it('takes the tip of its dart once the state holding it arrives', () => {
    const [placed] = placeOverlay(locatedDart(LINES, 0, 0), [dart('T20', [1, 2])], 1, 0);
    expect(placed.tip).toEqual([1, 2]);
    expect(placed.color).toBe(dartColor(0));
  });

  it('follows its dart when the visit is reordered', () => {
    const darts = [dart('5', [3, 3]), dart('T20', [1, 2])];
    const [placed] = placeOverlay(drawnAt(0, [1, 2]), darts, 2, 2);
    expect(placed.dartIndex).toBe(1);
    expect(placed.color).toBe(dartColor(1));
  });

  it('greys out a dart booked as another field by hand', () => {
    const darts = [dart('T5', null), dart('20', [3, 3])];
    const [placed] = placeOverlay(drawnAt(0, [1, 2]), darts, 2, 2);
    expect(placed.corrected).toBe(true);
    expect(placed.color).toBe(CORRECTED_DART_COLOR);
    expect(placed.polylines).toBe(LINES);
  });

  it('keeps a greyed out dart for the rest of the visit', () => {
    const corrected = placeOverlay(drawnAt(0, [1, 2]), [dart('T5', null)], 1, 1)[0];
    expect(placeOverlay(corrected, [], 0, 1)).toEqual([corrected]);
  });

  it('drops a dart that was taken out of the visit', () => {
    const darts = [dart('20', null)];
    expect(placeOverlay(drawnAt(0, [1, 2]), darts, 1, 2)).toEqual([]);
  });

  it('marks a dart beyond the booked ones as a shadow', () => {
    const darts = [dart('20', [3, 3]), dart('T20', [1, 2])];
    const [placed] = placeOverlay(drawnAt(1, [1, 2]), darts, 1, 2);
    expect(placed.color).toBe(SHADOW_DART_COLOR);
  });
});
