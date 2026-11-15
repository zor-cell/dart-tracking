/**
 * What this device does in the game: whether it films the board. Kept on the
 * server's client record and changed by a `set_role` command.
 */
export type DeviceRole = 'camera' | 'scoreboard';
