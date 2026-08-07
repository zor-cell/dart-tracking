import {
  NextPlayerCommand,
  RegisterDartCommand,
  UndoCommand
} from '../../../features/game/dto/game-command';

/** Client -> server messages, discriminated by `type`. */
export type OutgoingMessage =
  RegisterDartCommand
  | UndoCommand
  | NextPlayerCommand;
