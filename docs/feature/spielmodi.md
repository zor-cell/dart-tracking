# Spielmodi

Wie das Spiel gewertet wird, ist seit diesem Schritt eine eigene Achse neben dem
Modus (301/501/701) und dem Checkout: die **Variante**. Es gibt zwei, `x01` und
`elimination`.

Referenz-Implementierung:
`backend/src/app/api/features/game/domain/game.py`.

---

## 1. Die Regeln von Elimination

Gruppenspiel, mindestens zwei Spieler. Gezählt wird von **0 auf das Ziel hoch**
statt vom Modus herunter.

- **Eliminieren:** Trifft ein Spieler mit einem Dart die **exakte Punktzahl**
  eines Mitspielers, fällt dieser zurück auf 0. Beispiel: A steht auf 60, B auf
  30, B wirft D15 → B steht auf 60 und hat A eliminiert.
- **Pro Dart, nicht pro Visit.** Der Vergleich läuft nach jedem einzelnen Dart,
  ein Visit kann also drei Spieler nacheinander treffen.
- **Alle auf diesem Stand** werden zurückgesetzt, nicht nur einer.
- **Überschießen bustet**, wie in x01: der Visit verfällt und zählt nichts.
- **Checkout gilt auch hier.** Unter Double-Out muss der Dart, der das Ziel
  genau erreicht, ein Double sein; Ziel−1 bustet, weil kein Double von dort
  finishen kann.
- **Sieg:** wer das Ziel exakt erreicht.

### Der Bust räumt die Elimination mit ab

Eliminiert Dart 1 einen Mitspieler und überschießt Dart 3, verfällt der **ganze
Visit** — auch die Elimination. Das ist die konsequente Lesart von „ein
gebusteter Visit zählt nichts" und fällt im Replay (§2) auf `if turn.busted:
continue` zusammen. Die Gegenposition (Elimination bleibt stehen) wäre
vertretbar, würde aber verlangen, gebustete Turns für die Reset-Prüfung
trotzdem zu durchlaufen — zwei Wahrheiten darüber, was ein Bust bedeutet.

### Die Null ist ausgenommen

Zu Beginn stehen alle auf 0. Ohne Ausnahme würde der erste Fehlwurf — Punktzahl
bleibt 0 — das gesamte Feld „eliminieren". `_eliminate` steigt deshalb bei
`hit == 0` sofort aus. Die eine Zeile ist die einzige Sonderregel im Verfahren.

---

## 2. Elimination ist x01 gespiegelt

Der wichtigste Befund dieses Schrittes: mit den obigen Regeln rechnen beide
Varianten **identisch**, solange man nicht den Punktestand führt, sondern den
**Abstand zum Ziel** (`remaining`).

| | x01 | Elimination |
|---|---|---|
| Bust | `remaining < 0` | Überschießen ⟹ `remaining < 0` |
| Double-Out-Finish | `remaining == 0` braucht D | Ziel genau treffen braucht D |
| Double-Out-Sperre | `remaining == 1` bustet | Ziel−1 ist per D unerreichbar |
| Sieg | `remaining == 0` | Score == Ziel ⟹ `remaining == 0` |
| Checkout-Route | `checkout_route(remaining, …)` | dieselbe Funktion, gleiches Argument |

`_busts`, `winner`, `checkout`, `undo` und `next_player` sind deshalb
**unverändert** geblieben. Die gesamte Änderung an der Spiellogik ist, dass
`remaining()` von einer Summe zu einem Replay wird:

```python
def _scores(self) -> dict[int, int]:
    scores = {player.id: 0 for player in self.players}
    for turn in self.turns:
        if turn.busted:
            continue
        for dart in turn.darts:
            scores[turn.player_id] += dart.points
            if self.variant is GameVariant.ELIMINATION:
                self._eliminate(scores, turn.player_id)
    return scores
```

**Warum ein Replay und keine Summe.** Ein Reset hängt daran, wer *zum Zeitpunkt
des Wurfs* auf welchem Stand stand. Diese Information steckt nur in der
Reihenfolge, nicht in einer Summe pro Spieler. Das Replay ist damit die kleinste
Darstellung, die die Regel überhaupt ausdrücken kann.

**Nebenwirkung: Undo ist gratis korrekt.** Weil `remaining()` bei jedem Aufruf
neu aus den Turns rechnet, bringt das Zurücknehmen eines eliminierenden Darts den
zurückgesetzten Spieler automatisch wieder auf seinen alten Stand. Hätte der
Score als Feld am Spieler gelegen, wäre genau das die Stelle gewesen, an der
das Feature bricht — ein Reset ist nicht invertierbar, wenn man den Vorzustand
nicht mehr hat.

Für x01 tritt im Replay nie ein Reset ein, das Ergebnis ist also bitgleich zu
der Summe, die vorher dort stand.

### Die Anzeige

Das Frontend zeigt bei Elimination den **erreichten Stand**, nicht den Abstand:
`mode - remaining`. Deshalb braucht das `PlayerDto` kein zusätzliches Feld — die
Zahl, die auf der Karte steht, ist eine Ansichtssache und wird dort gebildet
(`GameComponent.score`).

---

## 3. Der Eliminations-Hinweis

Neben der Checkout-Route zeigt die Wurfreihe bei Elimination, womit sich ein
Mitspieler zurücksetzen lässt — dieselben Kästchen, aber **rot** statt grau.

**Die Route ist dasselbe Problem wie ein Checkout.** Um A auf Stand `S` zu
treffen, muss ich von meinem Stand `M` aus exakt `S − M` Punkte werfen. Das ist
die Frage, die `checkout_route` ohnehin beantwortet, mit zwei Unterschieden:

- **Kein Double nötig** (`double_out=False`): ein Reset ist kein Finish, jedes
  Feld zählt. Ein Konflikt mit der Double-Out-Regel kann nicht entstehen, denn
  ein Gegner auf dem Ziel hätte bereits gewonnen.
- **Kein Bust möglich:** `M + (S − M) = S`, und `S` liegt unter dem Ziel.

**Welcher Gegner.** Es können mehrere erreichbar sein. Gewählt wird der am
leichtesten zu treffende: wenige Darts zuerst, bei Gleichstand der kleinere
Abstand. Gegner *unter* meinem Stand entfallen — Darts addieren nur. Ein Abstand
von 0 entfällt ebenfalls, passend zur Null-Ausnahme aus §1: dort gibt es nichts
zu treffen.

**Sieg schlägt Reset.** Wenn beides möglich ist, füllen die Kästchen die
Checkout-Route. Die Rangfolge sitzt im Frontend (`checkout ?? elimination`),
nicht in der Domain — `GameStateDto` trägt beide Routen und bleibt damit eine
Zustandsbeschreibung statt einer Anzeigeentscheidung.

**Warum nicht beide gleichzeitig.** Eine Route ist eine *Sequenz über die
Kästchen* (`D20` in Slot 1, `20` in Slot 2). Zwei Sequenzen nebeneinander
(`16 / D20`) lesen sich nur, solange die rote genau einen Dart lang ist; ab
einem Bedarf über 60 braucht sie zwei, und beide Sequenzen parallel durch die
Slots zu führen wird mehrdeutig. Deshalb die Entweder-oder-Regel.

**Unterschieden wird allein über die Textfarbe** (Entscheidung): rot gegen das
gedämpfte Grau, Rahmen und Schriftschnitt bleiben identisch. Ein zusätzlicher
durchgezogener Rahmen war zwischenzeitlich drin, um nach WCAG 1.4.1 nicht nur
über Farbe zu unterscheiden, wurde aber zugunsten der ruhigeren Reihe verworfen.
Entschärft ist der Punkt dadurch, dass die Kästchen `aria-hidden` sind und die
Route nur ein Vorschlag ist — sie trägt keine Information, ohne die sich das
Spiel nicht führen lässt.

---

## 4. Wo die Variante überall hängt

| Stelle | Was |
|---|---|
| `domain/game_variant.py` | `StrEnum` mit `x01` / `elimination` |
| `domain/game.py` | Feld `variant`, `_scores()`, `_eliminate()`, `elimination` (§3) |
| `persistence/game.py` | Spalte `variant` (Migration `b17d4e9c05a2`, Bestand auf `x01` gesetzt) |
| `dto/game_config.py` | Eingabe beim Anlegen, Default `x01` |
| `dto/game_state.py` | geht an alle Geräte im Raum, inkl. `elimination` |
| Frontend `models/game-variant.ts` | Gegenstück, Werte identisch zur Wire-Form |
| `game-new.component` | Auswahl; die Modus-Auswahl heißt bei Elimination „Ziel" |
| `game.component` / `game-top-bar` | Anzeige des Stands, des Titels und der roten Kästchen |

Die CV-Pipeline (Kalibrierung, Erkennung, Socket, Kamera) ist **nicht**
betroffen: ein erkannter Dart ist in beiden Varianten derselbe `Dart`, nur die
Verrechnung unterscheidet sich.

---

## 5. Offene Punkte

- **Spieleliste.** `GameRepository.summaries` rechnet den Endstand als
  `mode - scored` direkt in SQL. Ein `SUM` kennt keine Resets, für
  Elimination-Spiele steht in der Historie also eine falsche Zahl. Der Fix ist
  eine zweite Query mit Turn-Reihenfolge und dasselbe Replay in Python —
  bewusst noch nicht gemacht, weil es die Liste umbaut.
- **Statistik.** `PlayerStatistics.add_leg` zählt pro Spieler herunter und sieht
  die Resets der anderen nicht; Checkout-Quote und Double-Quote wären damit
  falsch. Elimination-Legs werden deshalb vorerst **aus der Statistik
  ausgeschlossen** (`statistics_repository`). Average, Punkte und 180er wären
  für sich gültig und könnten später wieder mitzählen, sobald der Gewinner
  nicht mehr aus dem Countdown erschlossen wird.
- **Kein Eliminations-Feedback.** Dass man gerade zurückgesetzt wurde, sieht man
  nur daran, dass die Zahl auf 0 springt. Ein Feld am `GameStateDto` mit den
  zuletzt getroffenen Spielern wäre der Anknüpfungspunkt für eine Einblendung.
- **Nur eine Gruppenvariante.** Killer, Cricket und Around-the-Clock würden
  dieselbe Achse benutzen, aber anders als Elimination *nicht* mit der
  x01-Arithmetik zusammenfallen — dort bräuchte es echte Regel-Strategien
  statt eines Replays.
