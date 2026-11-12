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
      $localize`:@@game.rules.x01.3:Bei Double Out muss der letzte Dart ein Double oder das Bullseye sein.`,
      $localize`:@@game.rules.x01.4:Wer überwirft, bei Double Out auf 1 landet oder ohne Double auf null kommt, hat Bust: der Visit zählt nicht.`,
    ],
  },
  elimination: {
    rules: [
      $localize`:@@game.rules.elimination.1:Alle starten bei null und zählen hoch bis 301, 501 oder 701.`,
      $localize`:@@game.rules.elimination.2:Wer mit einem Dart genau auf den Punktestand eines anderen kommt, schickt diesen auf null zurück.`,
      $localize`:@@game.rules.elimination.3:Überwerfen ist ein Bust. Wer das Ziel genau trifft, gewinnt, bei Double Out mit einem Double.`,
      $localize`:@@game.rules.elimination.4:Bei Double Kill schickt nur ein Double oder das Bullseye zurück.`,
    ],
  },
  cricket: {
    rules: [
      $localize`:@@game.rules.cricket.1:Gespielt wird auf 20 bis 15 und Bull. Single zählt 1 Mark, Double 2, Triple 3; der äußere Bull 1, das Bullseye 2.`,
      $localize`:@@game.rules.cricket.2:Mit 3 Marks ist eine Zahl zu. Weitere Marks bringen ihren Wert als Punkte, solange ein Gegner sie noch offen hat.`,
      $localize`:@@game.rules.cricket.3:Standard: Wer alles zu hat und mindestens so viele Punkte wie jeder Gegner, gewinnt.`,
      $localize`:@@game.rules.cricket.4:Cut-Throat: Die Punkte gehen an die Gegner, die die Zahl noch offen haben. Die wenigsten Punkte gewinnen.`,
      $localize`:@@game.rules.cricket.5:Ohne Punkte: Wer zuerst alles zu hat, gewinnt.`,
    ],
  },
  killer: {
    rules: [
      $localize`:@@game.rules.killer.1:Jeder bekommt eine eigene Zahl und 3 oder 5 Leben.`,
      $localize`:@@game.rules.killer.2:Triffst du dein eigenes Feld, wirst du Killer.`,
      $localize`:@@game.rules.killer.3:Als Killer kostet jeder Treffer auf das Feld eines Gegners diesem ein Leben. Dein eigenes Feld kostet dich eins.`,
      $localize`:@@game.rules.killer.4:Bei „Ganze Zahl“ zählt jeder Ring: ein Double nimmt 2 Leben, ein Triple 3.`,
      $localize`:@@game.rules.killer.5:Wer keine Leben mehr hat, scheidet aus. Wer zuletzt noch Leben hat, gewinnt.`,
    ],
  },
  around_the_clock: {
    rules: [
      $localize`:@@game.rules.clock.1:Triff 1 bis 20 der Reihe nach, dann das Bull. Wer zuerst durch ist, gewinnt.`,
      $localize`:@@game.rules.clock.2:Bei Single zählt jeder Ring, bei Double oder Triple nur dieser; am Bull dann nur das Bullseye.`,
      $localize`:@@game.rules.clock.3:Mit Springen bringt ein Double zwei Felder weiter, ein Triple drei, aber nie am Bull vorbei.`,
    ],
  },
};
