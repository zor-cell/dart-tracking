import { GroupKind } from '../dto/accuracy.dto';

/** The technical properties the darts can be grouped by, in the order the picker offers them. */
export const GROUP_KINDS: readonly { readonly value: GroupKind; readonly label: string }[] = [
  { value: 'version', label: $localize`:@@eval.trackerVersion:Tracker-Version` },
  { value: 'tilt', label: $localize`:@@eval.tilt:Kameraneigung` },
  { value: 'fragments', label: $localize`:@@eval.group.fragments:Blob-Fragmente` },
];

/** How a group's code reads on the page: `20-35` as `20–35°`, `3+` as `3+ Fragmente`. */
export function groupLabel(kind: GroupKind, key: string): string {
  switch (kind) {
    case 'version':
      return key === 'unknown' ? $localize`:@@eval.unknown:unbekannt` : key;
    case 'tilt':
      return key.endsWith('+')
        ? $localize`:@@eval.group.tiltFrom:ab ${key.slice(0, -1)}:low:°`
        : `${key.replace('-', '–')}°`;
    case 'fragments':
      return key === '1'
        ? $localize`:@@eval.group.oneFragment:1 Fragment`
        : $localize`:@@eval.group.fragmentCount:${key}:count: Fragmente`;
    default:
      return key;
  }
}
