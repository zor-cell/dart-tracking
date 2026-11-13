import { GameVariant } from './game-variant';

/** A variant explained for the info dialog. */
export interface GameRules {
  readonly rules: readonly string[];
}

export const GAME_RULES: Readonly<Record<GameVariant, GameRules>> = {
  x01: {
    rules: [
      $localize`:@@game.rules.x01.1:Jeder startet mit 301, 501 oder 701 Punkten und zieht ab, was er wirft.`,
      $localize`:@@game.rules.x01.2:Wer genau auf null kommt, gewinnt.`,
      $localize`:@@game.rules.x01.3:Überwirft jemand, ist es ein Bust: der Visit zählt nicht.`,
    ],
  },
  elimination: {
    rules: [
      $localize`:@@game.rules.elimination.1:Alle starten bei null und zählen hoch bis 301, 501 oder 701.`,
      $localize`:@@game.rules.elimination.2:Wer mit einem Dart genau auf den Punktestand eines anderen kommt, schickt diesen auf null zurück.`,
      $localize`:@@game.rules.elimination.3:Überwerfen ist ein Bust. Wer das Ziel genau trifft, gewinnt.`,
    ],
  },
  cricket: {
    rules: [
      $localize`:@@game.rules.cricket.1:Gespielt wird auf 20 bis 15 und Bull. Single zählt 1 Mark, Double 2, Triple 3; die 25 zählt 1, das Bull 2.`,
      $localize`:@@game.rules.cricket.2:Mit 3 Marks ist eine Zahl zu. Weitere Marks bringen ihren Wert als Punkte, solange ein Gegner sie noch offen hat.`,
      $localize`:@@game.rules.cricket.3:Wer alles zu hat und bei den Punkten vorne liegt, gewinnt.`,
    ],
  },
  killer: {
    rules: [
      $localize`:@@game.rules.killer.1:Jeder bekommt eine eigene, zufällige Zahl und 3 oder 5 Leben.`,
      $localize`:@@game.rules.killer.2:Triffst du dein eigenes Feld, wirst du Killer.`,
      $localize`:@@game.rules.killer.3:Als Killer kostet jeder Treffer auf das Feld eines Gegners diesem ein Leben. Dein eigenes Feld kostet dich eins.`,
      $localize`:@@game.rules.killer.4:Wer keine Leben mehr hat, scheidet aus. Wer zuletzt noch Leben hat, gewinnt.`,
    ],
  },
  around_the_clock: {
    rules: [
      $localize`:@@game.rules.clock.1:Triff 1 bis 20 der Reihe nach, dann das Bull. Wer zuerst durch ist, gewinnt.`,
    ],
  },
};
