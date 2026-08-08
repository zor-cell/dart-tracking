/**
 * What this device does in the game (see docs/feature/multi-device.md §1).
 *
 * It is metadata of the connection: the device names it when opening the socket,
 * and the server keeps it on the room's connection. It says nothing about what
 * the device may change — a scoreboard is explicitly the way to correct a
 * misread — only whether it films the board.
 */
export type DeviceRole = 'camera' | 'scoreboard';
