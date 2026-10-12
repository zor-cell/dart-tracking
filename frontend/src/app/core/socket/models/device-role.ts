/**
 * What this device does in the game.
 *
 * It belongs to the device, not the connection: the server keeps it on the
 * client record, where it outlives the socket, and a `set_role` command is what
 * changes it. It says nothing about what the device may change — a scoreboard
 * is explicitly the way to correct a misread — only whether it films the board.
 */
export type DeviceRole = 'camera' | 'scoreboard';
