# Pfeil-Korrektur im offenen Visit

Wie ein falsch gebuchter Pfeil geradegerückt wird, ohne den Rest des Visits
mitzureißen: auswählen und überschreiben, verschieben, einzeln löschen.

Referenz-Implementierung: `Game.replace_dart` / `move_dart` / `remove_dart`
(`backend/src/app/api/features/game/domain/game.py`), Bedienung in
`frontend/src/app/features/game/components/game/`.
Wirkung auf die Messung: [auswertung.md §2/§3](../auswertung.md).

---

## 1. Warum nicht Undo

Undo ist ein Stapel: es nimmt den *letzten* Pfeil zurück. Jeder Fehler weiter
vorn im Visit kostet damit so viele Schritte, wie Pfeile danach kamen — und
jeder dieser Schritte wirft Information weg, die richtig war:

- die **Reihenfolge**: der nachgetippte Pfeil landet hinten, nicht dort, wo er
  geworfen wurde;
- die **Trefferpunkte** der zurückgenommenen Pfeile — sie werden von Hand neu
  eingegeben und haben danach keine Position mehr, fehlen also im virtuellen
  Board und in jeder Heatmap;
- die **Overlays** auf dem Kamerabild, die an ihren Pfeilen hängen.

Drei Fehlerbilder treten in der Praxis auf, und Undo ist für keines davon das
passende Werkzeug:

| Fall | Was passiert ist | Korrektur |
|---|---|---|
| **Fehlerkennung** | Kamera bucht T20, es steckt S20 | Pfeil auswählen, Feld neu tippen |
| **Nicht erkannt** | 20, 1, 5 geworfen, 1 und 5 gebucht | 20 von Hand nachtragen, nach vorn ziehen |
| **Phantom** | Buchung ohne Wurf, mitten im Visit | Pfeil auswählen, löschen |

---

## 2. Auswählen statt löschen

Ein Tipp auf einen gebuchten Pfeil **wählt ihn aus** (vorher: löschte ihn).
Ausgewählt heißt: der nächste Tastendruck auf dem Zifferblock schreibt dieses
Feld *an dieser Stelle*, statt hinten anzuhängen. Danach ist die Auswahl
verbraucht — der Tipp darauf hängt wieder an.

Zwei Dinge folgen daraus:

- **Der Zifferblock bleibt aktiv, wenn ein Pfeil ausgewählt ist**, auch bei
  vollem oder überworfenem Visit (`padAccepts`). Genau dort muss eine
  Fehlerkennung ja korrigierbar sein — der dritte Pfeil ist der häufigste Fall,
  und der Bust kann gerade das sein, was falsch ist.
- **Die Auswahl wird durch den offenen Visit gelesen**, nicht bloß gespeichert:
  gemerkt wird `{turn, index}`, und `selectedDart` gibt sie nur heraus, solange
  `turn` noch der offene Visit ist und der Index darin steckt. Sie kann damit
  keinen Pfeil überleben, den es nicht mehr gibt — und, wichtiger, nach einer
  Übergabe nicht wieder auftauchen: ein bloßer Index hätte sich an den Pfeil
  geheftet, der im *nächsten* Visit an dieselbe Stelle fällt.
- **Ein Tipp irgendwo sonst beendet die Auswahl.** Ausgewählt zu sein ist ein
  Modus, und ihn zu verlassen soll nicht den zweiten Tipp auf denselben Pfeil
  verlangen. Ein `pointerdown` auf dem Dokument räumt sie deshalb auf, sofern das
  Ziel weder in der Pfeil-Reihe noch im Zifferblock liegt — den beiden Blöcken,
  die etwas mit ihr tun. `pointerdown` und nicht `click`, damit das Aufräumen
  schon beim Aufsetzen des Fingers passiert und nicht erst beim Loslassen.

Der ersetzte Pfeil ist danach eine **Handbuchung ohne Trefferpunkt**. Das ist
die ehrliche Lesart: korrigiert wird, weil die Kamera das Segment falsch gelesen
hat, also ist auch ihr Punkt nicht zu trauen. `DartDto.position` bedeutet
unverändert „von der Kamera lokalisiert" (siehe
[multi-device.md §4a](multi-device.md)).

---

## 3. Zurück wird Löschen

Solange ein Pfeil ausgewählt ist, trägt die Zurück-Taste ein Mülleimer-Symbol
und nimmt **diesen** Pfeil heraus statt des letzten. Dieselbe Taste, weil sich
die beiden nie überschneiden: ein ausgewählter Pfeil ist der, den man ändern
will, und „einen Schritt zurück" ist dann keine sinnvolle Antwort — der Schritt
zurück würde einen anderen Pfeil treffen.

Das ist der Weg aus dem Phantom-Fall. Vorher hieß er: zweimal Undo, dann den
echten dritten Pfeil neu eintippen.

---

## 4. Ziehen ändert die Reihenfolge

Die drei Pfeil-Kästchen sind eine `cdkDropList` mit horizontaler Sortierung; ein
Kästchen lässt sich an eine andere Stelle ziehen. Serverseitig ist das
`move_dart(index, to_index)`.

**Warum die Reihenfolge überhaupt zählt**, wo die Summe doch dieselbe bleibt:

1. Das Alignment der Auswertung ist eine Sequenz-Ausrichtung über die Labels
   ([auswertung.md §3](../auswertung.md)). Position im Visit ist das, was
   „dieser Pfeil wurde verpasst" von „dieser Pfeil wurde falsch gelesen"
   trennt.
2. Das virtuelle Board und die Overlays auf dem Kamerabild nummerieren und
   färben nach Position (`dartColor`). Ein nachgetragener erster Pfeil, der
   hinten steht, färbt alle drei falsch.
3. Checkout-Vorschläge und die Bust-Regel hängen an der Reihenfolge, sobald ein
   Pfeil ins Minus führt.

`cdkDragStartDelay` steht auf 150 ms für Touch und 0 für Maus: ohne die
Verzögerung wird jeder Tipp auf ein Kästchen zum Beginn eines Zuges, und der
Tipp ist die häufigere Geste.

Nichts wird lokal umsortiert. Der Drop schickt das Kommando, der Server pusht
den neuen Zustand, die Liste rendert daraus — wie jede andere Änderung auch
(`docs/feature/done/persistenz.md`).

---

## 5. Serverseite: eine Regel für alle drei

Alle drei Kommandos laufen über `Game._rescore(darts)`: der offene Visit wird
verworfen und die übergebene Folge von vorn neu angewendet, inklusive
`_busts` pro Pfeil.

Das ist nicht Bequemlichkeit, sondern notwendig. Ob ein Pfeil überwirft, hängt
vom Reststand *vor* ihm ab, also von allen Pfeilen davor. Ein Tausch an
Position 0 kann den Bust an Position 2 erzeugen oder auflösen; ein Zug von hinten
nach vorn ebenso. Nur ein vollständiger Neudurchlauf kommt auf dieselbe Antwort
wie die ursprüngliche Buchung.

`replace_dart` und `move_dart` sind bewusst **nicht** durch „Visit voll" oder
„Spiel gewonnen" abgesichert — dieselbe Begründung wie bei `undo`: einen falsch
gebuchten Siegwurf zu korrigieren ist genau der Moment, in dem man es braucht.
`register_dart` bleibt abgesichert, denn dort geht es ums Anhängen, und ein
vierter Pfeil im Visit ist ein Fehltrigger.

**Nachtragen in einen geschlossenen Visit.** Die Handeingabe läuft seit 21.09.
nicht mehr über `register_dart`, sondern über `add_dart`: dieselbe Grenze von
drei Pfeilen, aber auch ein überworfener oder gewonnener (noch nicht bestätigter)
Visit nimmt Pfeile an, solange Platz ist. Der Fall: ein Pfeil wurde nicht
getrackt, der nächste überwirft oder checkt aus — ohne das wäre die Tastatur
gesperrt und der verpasste Pfeil nur über Undo nachzutragen.

Ein solcher Visit ist **durch seinen letzten Pfeil geschlossen**: ein Bust wird
immer vom letzten Pfeil ausgelöst, und nach einem Checkout wird nicht mehr
geworfen. Der nachgetragene Pfeil wird deshalb nicht angehängt, sondern vor den
letzten gesetzt (Stand 20: 5, 19 + 0 → 5, 0, 19; 2, D9 + 0 → 2, 0, D9). Hinten
angehängt würde eine 0 nach dem Checkout wegen Double-Out sogar als Bust zählen.
Gehört er noch weiter nach vorn, bringt ihn Ziehen (§4) dorthin; `_rescore`
entscheidet Bust und Sieg dabei jedes Mal neu, ein nachgetragener Pfeil, der vor
dem Double schon überwirft (2, 5, D9), macht aus dem Sieg also korrekt einen
Bust. Nach der Siegbestätigung ist die Tastatur ausgeblendet, wie bisher.

Die Kamera bleibt bei `register_dart`, ein Treffer nach dem Bust ist dort
weiterhin ein Fehltrigger. Im Frontend spiegelt `GameService.acceptsManualDarts`
die Regel.

---

## 6. Overlays folgen ihrem Pfeil

Die Umrisse auf dem Kamerabild hingen bisher an einem Index und wurden bei einer
Entfernung von Hand nachgezogen. Mit Ersetzen und Verschieben reicht das nicht
mehr, also hängen sie jetzt am **Trefferpunkt** in Board-Millimetern
(`RoundDartOverlay.tip`, `place()` in `detection.service.ts`):

- Ein frischer Umriss übernimmt den Punkt aus dem Pfeil, den der Server an
  seiner Stelle gebucht hat — der `detection_result` trägt ihn nicht selbst, er
  spricht bewusst nur die Bildkoordinaten dieser Kamera.
- Danach wird er bei jedem `game_state` über diesen Punkt wiedergefunden. Damit
  stimmen Nummer und Farbe nach Löschen, Ersetzen und Verschieben von selbst.
- Ein korrigierter Pfeil hat keinen Punkt mehr, sein Umriss fällt also heraus.
  Das ist gewollt: der gezeichnete Punkt ist dann keiner mehr, den das Spiel
  behauptet.

Ersetzt wurde damit auch die alte Heuristik `removedIndex`, die den entfernten
Pfeil über den ersten Unterschied der beiden Listen suchte — zwei gleiche Pfeile
im Visit konnten sie verwirren.

---

## 7. Schatten-Darts nach Sieg oder Bust

**Problem.** Ein Checkout auf D18 landet knapp daneben, die Kamera liest D18.
Der Visit ist damit gewonnen, `register_dart` nahm bis 25.09. nichts mehr an, und
das Kamera-Handy schickte gar keine Frames mehr („Tracking pausiert"). Die
beiden folgenden Pfeile wurden nicht erkannt; wer die D18 korrigierte, musste
sie von Hand nachtragen oder neu werfen. Dasselbe bei einem fälschlich
erkannten Bust. Nebenbei blieb das Referenzbild des Servers auf dem Stand vor
den beiden Pfeilen stehen.

**Lösung.** Ist der offene Visit durch Sieg oder Bust geschlossen, aber noch
nicht bestätigt, trackt die Kamera weiter, solange weniger als drei Pfeile
physisch im Board stecken (gebuchte + Schatten). `Game.register_dart` legt
solche Pfeile in `Game.shadow_darts` ab statt in den Visit; sie zählen nicht,
werden nicht angesagt, und alle Geräte zeigen sie ausgegraut: gestrichelt in
den freien Slots der Dart-Zeile, blass auf der virtuellen Scheibe, grau im
Kamera-Overlay.

**Nachbuchen.** Jede Korrektur, die den Visit wieder öffnet — Ersetzen,
Löschen, Verschieben, manuelles Hinzufügen, Undo —, bucht die Schatten-Darts in
Wurfreihenfolge ein, solange der Visit offen bleibt
(`Game._book_shadow_darts`). Aus „D18 · (5) · (D9)" wird durch Umbuchen der
D18 auf 18 also direkt „18 · 5 · D9" mit korrekt neu entschiedenem Bust bzw.
Sieg. Es gilt dieselbe Regel wie in §5: der Server bucht, das Frontend zeigt
nur an.

**Randregeln.**

- *Obergrenze drei Pfeile.* Gebuchte plus Schatten-Darts übersteigen nie drei.
  Macht eine manuelle Buchung den Visit voller, fällt der letzte Schatten-Dart
  weg — die Handeingabe sagt, dass der Nutzer es besser weiß.
- *Undo* nimmt weiterhin den letzten **gebuchten** Pfeil, nicht einen
  Schatten-Dart: der typische Griff zur Zurück-Taste gilt genau dem Pfeil, der
  den Visit fälschlich geschlossen hat.
- *Bestätigen verwirft.* `next_player` leert die Liste; ein richtig erkannter
  Sieg wird clientseitig bestätigt, danach pausiert das Tracking wie bisher.
- *Automatisches Weiterschalten* (Bestätigen aus) kennt keinen Schattenzustand:
  nach einem Bust ist sofort der nächste Spieler dran.

**Speicher.** Nur der offene Visit kann Schatten-Darts haben, deshalb eine
JSON-Spalte `games.shadow_darts` statt einer Spalte in `game_darts` — die
Statistik-Abfragen auf `game_darts` bleiben unberührt.

**Auswertung.** Ein Schatten-Dart wird wie ein absorbierter Pfeil als
`detected` mit `accepted = false` geloggt; wird er nachgebucht, folgt ein
`shadow_booked` ([auswertung.md §2](../auswertung.md)), das der Replay als
Kamera-Behauptung und als Buchung zählt.

---

## 8. Offene Punkte

- **Referenzbild nach einer Korrektur.** Unverändert das offene Problem aus
  `docs/status/todo.md`: eine Handbuchung — und damit auch eine Korrektur —
  ändert nichts am Referenzframe, das Board zeigt aber weiterhin drei Pfeile.
- **Kein Ziehen über die Visit-Grenze.** Ein Pfeil, der im falschen Visit
  gelandet ist, braucht weiterhin Undo.
- **Auswahl ist gerätelokal.** Zwei Geräte können denselben Pfeil ausgewählt
  haben und ihn nacheinander überschreiben. Der Server serialisiert das
  (`_apply` unter Row-Lock), es gewinnt also der zweite; angezeigt wird es nicht.
