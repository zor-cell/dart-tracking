# Live-Auswertung der Tracking-Genauigkeit

Wie aus einem normal gespielten Abend eine belastbare Genauigkeitszahl wird:
was mitgeschrieben wird, warum Korrekturen nicht gezählt, sondern *ausgerichtet*
werden, und welche Zahlen am Ende herausfallen.

Baut auf der Detektion auf ([erkennung.md](erkennung.md)) und ergänzt deren
Offline-Auswertung auf dem festen Testset um eine, die während des Spiels
entsteht.

Referenz-Implementierung: `backend/src/app/api/features/evaluation/`,
Report: `backend/scripts/evaluation/report.py`.

> **Stand:** Umgesetzt und gegen die Datenbank verifiziert, aber noch nicht mit
> echten Spieldaten gefüttert. Die Zahlen in §7 kommen, sobald der erste
> Praxis-Testlauf gelaufen ist.

---

## 1. Die Ausgangsfrage

Beim Spielen mit Freunden liegt die Wahrheit vor: wir sehen, was steckt.
Übernehmen wir alle drei Pfeile, hat der Tracker richtig gelegen; nehmen wir
einen zurück, nicht. Das ist eine Ground Truth, die zum Nulltarif entsteht — im
Gegensatz zu den `ground_truth.txt`-Dateien des Testsets, die von Hand gegen die
Videos geschrieben wurden.

**Nur ist sie nicht direkt ablesbar.** Beispiel: geworfen 25, 16, 8. Der Tracker
bucht 25, 8, 0, weil er die 16 gar nicht gesehen hat und später ein
Phantom-Trigger hinterherkommt. Um das zu korrigieren, drückt man zweimal
Zurück und tippt 16 und 8 nach. Wer Korrekturen zählt, misst hier **zwei bis
drei Fehler** — tatsächlich hat der Tracker *einen* Pfeil verpasst und *einen*
erfunden, und die 8 hat er richtig erkannt, nur an der falschen Stelle der
Reihenfolge.

Eine Undo-Zählung überschätzt den Fehler also systematisch, und zwar umso mehr,
je früher im Visit er passiert.

---

## 2. Das Event-Log

Die erste Voraussetzung ist, dass die Behauptung des Trackers überhaupt erhalten
bleibt. Sie tut es heute nicht:

- `Game.undo()` poppt den Dart aus dem Turn,
- `GameRepository.save` schreibt Turns und Darts bei jedem Zug **komplett neu**
  (`DELETE` + Insert).

Nach der Korrektur steht in `turns`/`darts` nur noch das Ergebnis. Deshalb ein
zweiter, **append-only** Kanal: `tracking_events`, eine Zeile pro Schritt, nie
aktualisiert, nie gelöscht.

| Kind | Wann |
|---|---|
| `detected` | die Kamera hat einen Pfeil gebucht |
| `detection_failed` | die Kamera hat gesucht und nichts gefunden |
| `manual` | ein Gerät hat einen Pfeil von Hand gebucht |
| `undo` | ein Schritt zurück |
| `next_player` | Visit abgeschlossen |

Jede Zeile trägt Feld (`value`/`multiplier`), Trefferpunkt in Board-Millimetern,
den Visit-Index, ob das Spiel die Aktion überhaupt angenommen hat (`accepted` —
ein vierter Dart im Visit wird geschluckt), und bei einer Detektion die
Kennzahlen des Detektors (`fragment_count`, `dart_length_mm`,
`alignment_shift_px`, … aus dem `DetectionTrace`).

**Atomar mit dem Zustand.** Der Event wird in derselben Transaktion angehängt,
in der die Spieländerung committet (`_apply(game_id, mutate, record)` in
`core/socket.py`). Ein Log, das gegenüber dem Zustand driftet, wäre als Messgerät
wertlos.

**Immer an.** Ein paar hundert Zeilen pro Spiel, wenige Kilobyte — der Schalter
in den Einstellungen betrifft nur die Bilder (§4). Ein vergessener Schalter darf
keinen Testabend kosten.

**Nicht geloggt** werden `invalid_image` und `not_calibrated`: beides entsteht
vor dem Fit und sagt nichts über die Erkennung. Ebenso wenig die Detektionen der
*nicht* scorenden Kamera — nur eine bucht (`scoring_camera`), also ist auch nur
eine messbar.

---

## 3. Alignment statt Korrekturzählung

Pro Visit stehen zwei Listen gegeneinander:

- **Behauptung** — alle Darts, die die Kamera in diesen Visit gebucht hat,
  *inklusive der zurückgenommenen*.
- **Wahrheit** — die Darts, die am Ende stehen, also das, was die Spieler mit
  „Wurf bestätigen" abgenickt haben.

Darauf ein Sequenz-Alignment (Needleman-Wunsch über die Segment-Labels). Das
obige Beispiel:

```
Behauptung:  25    —     S8   MISS
Wahrheit:    25   S16    S8    —
           korrekt missed korrekt phantom
```

**Zwei korrekt, einer nicht erkannt, einer erfunden** — statt „zwei bis drei
Fehler".

### Die Kostenwahl ist der ganze Trick

`_SUBSTITUTION_COST = 2`, `_GAP_COST = 1`. Mit den üblichen
Levenshtein-Kosten (Substitution = Lücke = 1) käme dasselbe Beispiel als *zwei
Substitutionen* heraus, also als zwei falsch gescorte Pfeile — die verpasste
Erkennung verschwände in der Statistik.

Weil eine Substitution genau so viel kostet wie das Paar aus Löschung und
Einfügung, entscheidet der Gleichstand. Er wird **zugunsten der Diagonale**
gebrochen, damit ein schlichter Fehlscore (gleiche Länge, ein Feld daneben)
`wrong` bleibt und nicht in `phantom` + `missed` zerfällt. Ein Versatz dagegen
ist echt billiger als die Substitutionskette und wird als solcher erkannt.

Die vier Ausgänge:

| Ausgang | Bedeutung | Ursache |
|---|---|---|
| `correct` | richtiges Feld gebucht | — |
| `wrong` | gebucht, falsches Feld | Detektionsgenauigkeit |
| `missed` | geworfen, nie gebucht | Trigger-Recall oder Detektion |
| `phantom` | gebucht ohne Pfeil dahinter | Trigger-Präzision |

Das ist dieselbe Konstruktion wie die Word Error Rate in der Spracherkennung —
für die Arbeit also zitierbares Standardverfahren und keine Eigenbau-Metrik.

### Der Replay

`visit_replay.replay` spielt das Log durch und bildet dabei `Game.undo`
nach — auch die Regel, dass ein Undo im leeren Visit die Übergabe mit
zurücknimmt und den *vorherigen* Visit anfasst. Visits werden dabei über ihren
**Slot** adressiert, nicht über eine Identität: geht ein Undo über die Grenze
zurück, verschwindet der offene Visit, und die nächste Übergabe öffnet denselben
Slot wieder — derselbe Spieler, der noch einmal wirft. Die Behauptungsliste
dieses Slots bleibt dabei stehen, sonst gingen genau die Fehlbuchungen verloren,
um die es geht.

### Abgrenzung gegen Spiele ohne Kamera

Ein rein von Hand gespielter Visit darf nicht als „drei nicht erkannt" zählen.
Ein Visit wird deshalb nur gewertet, wenn er **gefilmt** war: mindestens eine
Detektion (erfolgreich oder nicht), oder das `camera_armed`-Flag der Übergabe,
die ihn geöffnet hat. Letzteres deckt den Fall ab, dass die Kamera lief, aber
kein einziger Trigger kam — sonst wäre der schlimmste Recall-Fall unsichtbar.

### Bekannte Unschärfen

- Ein Undo aus einem anderen Grund (falscher Spieler dran, versehentliche
  Eingabe) zählt als Korrektur. Rauschen, das die Quote nach unten zieht.
- Ein Undo, das über eine bereits abgeschlossene Visit-Grenze zurückgreift,
  ändert die Wahrheit eines Visits, dessen Bilder schon verworfen sind (§4).
  Die Zahl bleibt richtig, nur die Bilder fehlen.
- `MANUAL` ist nicht von „Korrektur" zu unterscheiden, wenn jemand ohnehin
  von Hand mitschreibt. Deshalb die Kamera-Bedingung oben.

---

## 4. Bilder: nur die Fehlerfälle

Der `FrameBuffer` hält die Frames des offenen Visits im Speicher — das
Kalibrierungsbild des leeren Boards als `base`, dann jeden gescorten Wurf. Bei
`next_player`:

- **korrigiert** und das Spiel ist als Testlauf markiert → die Serie wird nach
  `backend/testdata/detection/live_<game-id>/` geschrieben, als
  `turnNNN_base.jpg` + `turnNNN_dartK.jpg`;
- **unverändert übernommen** → verworfen.

Das ist der Grund für die Aufteilung des Schalters: die akzeptierten Visits sind
die, die der Tracker schon kann, und sie machen den Großteil aus. Bei ~10 %
Speicherbedarf liefert der Puffer genau die Fälle, die das Testset noch nicht
enthält.

**Nur Frames, die der Fit erreicht hat.** Eine fehlgeschlagene Detektion lässt
den Referenz-Frame stehen; eine Serie, die sie enthielte, würde offline anders
verkettet als sie live war (`run_all.py` verkettet jedes aufeinanderfolgende
Paar).

**`ground_truth.txt` schreibt der Report, nicht der Server.** Welches Label zu
welchem Frame gehört, folgt erst aus dem Alignment — ein Frame ohne Partner in
der Wahrheit ist ein Phantom und bekommt `MISS`, ein Wahrheits-Label ohne Frame
(`missed`) fällt weg. Damit landen die Serien im Format, das
`scripts/detection/run_all.py` unverändert liest, und ein korrigierter Visit
wird ohne eine einzige Handmarkierung zum Testfall.

---

## 5. Der Schalter

Ein `evaluation_enabled` am Spiel, nicht am Gerät — gemessen wird das Spiel.
Gesetzt wird es an zwei Stellen:

- beim Anlegen aus der Geräte-Einstellung „Testlauf aufzeichnen"
  (localStorage, wie die Debug-Schalter),
- im laufenden Spiel über den Socket-Befehl `set_evaluation`, den derselbe
  Schalter mitschickt, wenn gerade ein Spiel offen ist.

Was er steuert: **nur die Bilder.** Event-Log und Detektor-Kennzahlen laufen
immer mit.

---

## 6. Der Report

```bash
uv run python scripts/evaluation/report.py              # alle Testläufe
uv run python scripts/evaluation/report.py --all-games  # alle geloggten Spiele
uv run python scripts/evaluation/report.py <game-id>
```

Schreibt `accuracy.md` nach `testdata/detection/_results_live/` und je Spiel dessen
`ground_truth.txt` in den Bilderordner. Der Ordnername folgt der Konvention des
Offline-Runners (`<board>_setup<n>`): alle Live-Aufnahmen gruppieren unter dem
„Board" `live`, jedes Spiel ist ein eigenes Setup.
Der Aufbau folgt bewusst dem Offline-Report (`erkennung.md §4`), damit Live- und
Testset-Zahlen nebeneinander lesbar sind:

- Kopfzahlen: geworfene Pfeile, gebuchte Pfeile, **korrektes Segment in %**,
  und der Anteil der **ohne Korrektur übernommenen Visits** — die Zahl, die dem
  Spielgefühl am nächsten kommt.
- Fehleraufschlüsselung nach den vier Ausgängen aus §3.
- **`off by` in Millimetern** für jeden Fehlscore: Abstand der gescorten Spitze
  zum nächsten Punkt des erwarteten Segments (`distance_to_segment`). Das trennt
  die zwei Fehlerarten, die eine reine Label-Quote gleich aussehen lässt —
  wenige Millimeter heißt „falsche Seite eines Drahts", zig Millimeter heißt
  „der Fit saß auf etwas anderem". Exakt dieselbe Spalte wie offline.
- **Kohäsions-Tabelle**: Quote gegen die Zahl der Fragmente, aus denen der Pfeil
  zusammengesetzt werden musste — die Live-Entsprechung der Messung aus
  [erkennung-blob.md](erkennung-blob.md).
- Leer zurückgekommene Detektionen nach Failure-Typ (`no_change`,
  `alignment_failed`, `implausible_shape`) — das Maß für die Trigger-Qualität,
  zu der [client-diff-verbesserungen.md](client-diff-verbesserungen.md) gehört.
- Mismatch-Liste, nach Abstand aufsteigend.

---

## 7. Offene Punkte

- **Noch keine echten Daten.** Verifiziert ist der Weg (Log → Replay →
  Alignment → Report) gegen die Datenbank, mit einem synthetischen Spiel. Die
  erste Messreihe kommt aus dem Praxis-Testlauf.
- **Kein Setup-Begriff.** Offline gruppiert die Auswertung nach Board und Setup
  (`pz_setup1`); live ist ein Spiel die kleinste Einheit. Solange ein Abend =
  ein Kamera-Aufbau ist, deckt sich das; sonst braucht es ein Feld dafür.
- **Latenz ungemessen.** Die Zeitstempel des Logs geben den Abstand zwischen
  Trigger und Buchung her, ausgewertet wird er noch nicht.
- **`FrameBuffer` wird nie geleert.** Prozesslokal und an kein Spielende
  gebunden, wie `detection_store` auch — rund ein Megabyte je Spiel, das bis zum
  Neustart liegen bleibt.
- **Doppelkamera.** Nur die scorende Kamera wird gemessen. Die zweite liefert
  bereits die unabhängige Zweitbeobachtung, aus der eine Fusion gebaut würde
  ([multi-device.md §5](done/multi-device.md)); ihre Trefferquote gegen dieselbe
  Wahrheit zu messen wäre der nächste Schritt.
