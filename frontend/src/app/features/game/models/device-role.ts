/**
 * What this device does in the game (see docs/feature/multi-device.md §1).
 *
 * Purely device-local: it decides whether this device films the board, not what
 * it may change about the game — a scoreboard is explicitly still the way to
 * correct a misread.
 */
export type DeviceRole = 'camera' | 'scoreboard';
