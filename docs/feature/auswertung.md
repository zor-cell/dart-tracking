# Live-Auswertung der Tracking-Genauigkeit

Wie aus einem normal gespielten Abend eine belastbare Genauigkeitszahl wird:
was mitgeschrieben wird, warum Korrekturen nicht gezählt, sondern *ausgerichtet*
werden, und welche Zahlen am Ende herausfallen.

Baut auf der Detektion auf ([erkennung.md](done/erkennung.md)) und ergänzt deren
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

*(Die Undo-Kaskade in diesem Beispiel ist inzwischen nicht mehr der Weg: ein
falsch gebuchter Pfeil wird an Ort und Stelle korrigiert, siehe
[korrektur.md](done/korrektur.md). Am Maßproblem ändert das nichts — auch
Korrekturen zu zählen überschätzt den Fehler, und das Alignment unten bleibt die
Antwort darauf.)*

---

## 2. Das Event-Log

Die erste Voraussetzung ist, dass die Behauptung des Trackers überhaupt erhalten
bleibt. Sie tut es heute nicht:

- `Game.undo()` poppt den Dart aus dem Turn,
- `GameRepository.save` schreibt Turns und Darts bei jedem Zug **komplett neu**
  (`DELETE` + Insert).

Nach der Korrektur steht in `game_turns`/`game_darts` nur noch das Ergebnis.
Deshalb ein zweiter, **append-only** Kanal: `game_events`, eine Zeile pro
Schritt, nie aktualisiert, nie gelöscht.

| Kind | Wann |
|---|---|
| `detected` | die Kamera hat einen Pfeil gebucht; `accepted = false`, wenn er nach Sieg/Bust nur als Schatten-Dart ankam |
| `shadow_booked` | eine Korrektur hat den Visit wieder geöffnet und einen Schatten-Dart nachgebucht ([korrektur.md §7](done/korrektur.md#7-schatten-darts-nach-sieg-oder-bust)) |
| `detection_failed` | die Kamera hat gesucht und nichts gefunden |
| `manual` | ein Gerät hat einen Pfeil von Hand gebucht |
| `undo` | ein Schritt zurück |
| `dart_removed` | ein einzelner Pfeil aus dem offenen Visit genommen (`dart_index`) |
| `dart_replaced` | ein einzelner Pfeil auf ein anderes Feld umgebucht (`dart_index` + Feld) |
| `dart_moved` | ein Pfeil an eine andere Stelle im Visit gezogen (`dart_index` → `target_index`) |
| `next_player` | Visit abgeschlossen |
| `calibrated` | die scorende Kamera hat kalibriert; `metrics` trägt ihren Blickwinkel (§8) |

Jede Zeile trägt Feld (`value`/`multiplier`), Trefferpunkt in Board-Millimetern,
den Visit-Index, ob das Spiel die Aktion überhaupt angenommen hat (`accepted` —
ein vierter Dart im Visit wird geschluckt), und bei einer Detektion die
Kennzahlen des Detektors (`fragment_count`, `dart_length_mm`,
`alignment_shift_px`, … aus dem `DetectionTrace`).

**Atomar mit dem Zustand.** Der Event wird in derselben Transaktion angehängt,
in der die Spieländerung committet (`_apply(game_id, mutate, record)` in
`core/socket.py`). Ein Log, das gegenüber dem Zustand driftet, wäre als Messgerät
wertlos. Preis dieser Kopplung: ein Fehler beim Schreiben des Events rollt den
Wurf mit zurück. Deshalb castet `recorder.metrics_of` jeden Wert auf `float` —
ein numpy-Skalar aus dem Trace wäre in JSONB nicht serialisierbar und würde
nicht bloß die Messung, sondern den Dart kosten.

**Eine Tür für den Socket.** Alles, was der Socket dafür tun muss, steht in
`services/recorder.py`: welche Events ein Kommando hinterlässt, welche Fehlschläge
zählen, wann Frames geschrieben werden. `socket.py` kennt davon nur den Namen
`recorder` — die Auswertung ist damit an einer Stelle abschaltbar und an einer
Stelle zu lesen, statt über zwölf Aufrufstellen verteilt.

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

`shadow_booked` geht in **beide** Listen: es ist eine Behauptung der Kamera,
die erst mit der Korrektur zur Buchung wird. Es steht im Log direkt hinter dem
Korrektur-Event, das den Visit geöffnet hat.

`dart_removed`, `dart_replaced` und `dart_moved` fassen **nur die
Wahrheitsliste** an — herausnehmen, an Ort und Stelle überschreiben,
umsortieren. Die Behauptungsliste bleibt unberührt, sonst ginge genau die
Fehlbuchung verloren, um die es geht. Das sind die drei Korrektur-Gesten aus
[korrektur.md](done/korrektur.md), und jede spart die Undo-Kaskade, die den Rest
des Visits mitgerissen hätte:

- *8 · Phantom-0 · 16:* ein Tipp auf die 0 und Löschen entfernt sie; die 16
  bleibt als erkannter Pfeil mit Trefferpunkt stehen, statt von Hand und ohne
  Position neu eingegeben zu werden. Das Alignment zählt die 0 weiterhin als
  `phantom`.
- *T20 statt S20:* der Pfeil wird überschrieben, die Behauptung T20 bleibt
  stehen. Das Paar liest sich als `wrong`, und weil der Trefferpunkt am
  `detected`-Event hängt und nicht am Spielzustand, bleibt auch `off_by_mm`
  messbar.
- *Verpasster erster Pfeil:* von Hand nachgetragen landet er hinten und wird
  nach vorn gezogen. An den Stückzahlen ändert das nichts — das Alignment
  findet die Lücke so oder so — wohl aber an der Position, unter der der
  verpasste Pfeil im Report steht.

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
  `dart_replaced` dagegen ist immer eine: es gibt nichts zu überschreiben,
  was nicht schon gebucht war.
- **Die Behauptungsliste ist kumulativ.** Nach einem Undo ist der Platz im Visit
  wieder frei, die Kamera bucht also erneut hinein — die Liste wird länger als
  drei. Das ist gewollt (jede Fehlbuchung soll gezählt werden), heißt aber: liest
  die Kamera denselben Pfeil nach einer Korrektur ein zweites Mal richtig, zählt
  dieser zweite Versuch als `correct`. Im ersten echten Testlauf trat das nicht
  auf — dort waren die überzähligen Buchungen echte Fehltrigger vor dem Wurf
  (Visit 0 von `01a07b48`: dreimal `MISS` plus ein `implausible_shape`, danach
  die drei echten Pfeile korrekt).

### 3a. Die gelesene Null zählt nicht

Ein `no_change` heißt: die Kamera hat hingesehen und nichts Neues am Board
gefunden — der Pfeil ist abgeprallt oder blieb nicht stecken. Das ist
punktemäßig dasselbe wie ein `MISS`, und offline zählt `run_all.py` es deshalb
als korrekt ([erkennung.md §3](done/erkennung.md)). **Live nicht.** Ein `no_change`
zählt als `missed`.

Der Weg dorthin ging über zwei verworfene Varianten, beide lehrreich.

**Verworfen: der Detektor gibt null Punkte zurück.** Dann bräuchte es beim
Judging keine Sonderregel — es stünde eine gebuchte Null im Log. Es geht aber
nicht: die client-seitige Frame-Differenz ist auf Recall ausgelegt und löst auch
ohne Wurf aus. Der Detektor kann „Wurf fand statt, blieb nicht stecken" nicht von
„es gab keinen Wurf" unterscheiden, und eine automatisch gebuchte Null wäre ein
Phantom-Pfeil, der eine Aufnahme verbraucht. Im Log steht das Gegenbeispiel: in
`01a07b67`, Visit 8, sitzt ein `no_change` mitten in einer Serie mit drei echten
Pfeilen. Deshalb bucht der Server nichts, und wer einen abgeprallten Pfeil hat,
trägt die Null von Hand ein.

**Verworfen: beim Judging rückwirkend gutschreiben.** Buchen die Spieler im
selben Visit eine Null, ist ja belegt, dass ein Wurf stattfand — man könnte das
`missed`-Paar also nachträglich zu `correct` machen. Das war kurzzeitig
implementiert und hob die Quote von 40 auf 41 von 54 (74.1 % → 75.9 %).

*Warum trotzdem verworfen:* die Quote beantwortet „wie oft wertet das System
selbst richtig". Ein `no_change` wertet nichts — ein Mensch musste die Null
eintippen. Es gutzuschreiben schönt genau die Größe, um die es geht, und zwar in
die angenehme Richtung. Dass die Wertung am Ende stimmt, ist ein Verdienst des
Spielers, nicht des Trackers.

**Offline zählt derselbe Vorgang anders — und das ist richtig so.** Zwei
verschiedene Fragen:

| | Frage | Bei leerem Board |
|---|---|---|
| `run_all.py` (offline) | Hat die Pipeline dieses Frame-Paar richtig *gelesen*? | `NO_CHANGE` ist die richtige Lesung → **korrekt** |
| `report.py` (live) | Hat das System selbst *gewertet*? | Es hat nichts gewertet, die Null kam von Hand → **`missed`** |

Es ist also kein Schlamperei-Unterschied, den man wegvereinheitlichen müsste,
sondern folgt aus dem, was jede Zahl beantwortet. Wer eine der beiden Quoten
nennt, muss nur sagen, welche Frage sie beantwortet.

**Ausgewiesen wird es trotzdem.** `missed_zeros` zählt die `missed`-Pfeile, die
die Spieler als Null eingetragen haben. Sie bleiben `missed`, sind aber eine
eigene Klasse: abgeprallt, heruntergefallen oder außerhalb des Bildes — ein
Pfeil, der gar nicht im Board steckt, ist weit schwerer zu erkennen als einer,
der steckt und falsch gelesen wurde. Die Auswertungsseite zeigt die Zahl unter
„Verpasst", `report.py` unter der Fehleraufschlüsselung.

Was daran *doch* zu reparieren war, lag woanders: offline trugen „nichts zu
sehen" und „Pfeil steckt im Surround" beide das Label `MISS`, sodass eine
verpasste Detektion einen Treffer bekam, sobald der Pfeil außerhalb der Wertung
steckte. Seit `NO_CHANGE` ein eigenes Ground-Truth-Label ist, ist das getrennt
([erkennung.md §3](done/erkennung.md)); die Offline-Quote fiel dadurch von 227 auf
**226 / 285** — ein Pfeil, der vorher zu Unrecht als Treffer galt.

---

## 4. Bilder: jeder Visit eines Testlaufs

Der `FrameBuffer` hält die Frames des offenen Visits im Speicher — das
Kalibrierungsbild des leeren Boards als `base`, dann jeden gescorten Wurf. Bei
`next_player`:

- **Spiel als Testlauf markiert** → die Serie wird nach
  `testdata/evaluation/game_<game-id>/` geschrieben, als
  `throwN_base.jpg` + `throwN_dartK.jpg`, egal ob korrigiert oder nicht;
- **sonst** → verworfen.

Anfangs wurden nur korrigierte Visits geschrieben, mit der Begründung, ein
übernommener Visit habe nichts zu lehren. Das hielt nicht: ohne die korrekt
gewerteten Serien lässt sich eine Änderung am Detektor offline nur gegen ihre
Fehlerfälle prüfen, nicht dagegen, ob sie einen vorher richtigen Pfeil kostet.
Der Testlauf-Schalter ist ohnehin schon die Entscheidung „dieses Spiel
aufzeichnen".

Das `game_`-Präfix sagt, wofür die UUID steht, und fällt zugleich mit der
`<board>_setup<n>`-Aufteilung des Offline-Runners zusammen: alle aufgezeichneten
Setups gruppieren dort unter dem „Board" `game`.

`N` ist der Visit-Index aus dem Event-Log, nicht durchnummeriert: `throw3` ist
die vierte Runde des Spiels, und dass `throw2` fehlt heißt, dass die Kamera in
dieser Runde nichts gescort hat. So lässt sich eine Bilderserie ohne Umweg der Zeile im Log
zuordnen. Den Namen vergibt `frame_buffer.series_name`, die auch der Report
benutzt — die beiden dürfen nicht auseinanderlaufen.

**Eigener Baum, kein Unterordner von `detection/`.** Diese Serien sind
aufgezeichnet, nicht kuratiert. `run_all.py` nimmt den zu durchlaufenden Ordner
als Argument, liest das Format aber unverändert:

```bash
uv run python scripts/detection/run_all.py testdata/evaluation
```

Kein `--raw` nötig: die Frames liegen schon so vor, wie der Client sie sendet
(max. 1280 px, JPEG q85), und `as_client_would_send` reicht ein Bild innerhalb
der Aufnahmegröße unverändert durch. Vorher komprimierte es blind ein zweites
Mal, was auf diesen elf Pfeilen **81.8 % → 54.5 %** kostete — siehe
[erkennung.md §6](done/erkennung.md), wo derselbe Effekt auf dem kuratierten Testset
gemessen ist.

Das ist der Grund für die Aufteilung des Schalters: die akzeptierten Visits sind
die, die der Tracker schon kann, und sie machen den Großteil aus. Bei ~10 %
Speicherbedarf liefert der Puffer genau die Fälle, die das Testset noch nicht
enthält.

**Genau die Frames, die die Referenz weitergerollt haben.** `run_all.py`
verkettet jedes aufeinanderfolgende Paar, die Serie muss also dieselbe Kette
enthalten wie live. Eine fehlgeschlagene Detektion lässt die Referenz stehen und
fehlt deshalb. Drei Arten gehören hinein, festgehalten in `throwN_frames.txt`
(`FrameKind` in `frame_buffer.py`):

| Art | Wann | Label im Report |
|---|---|---|
| `booked` | Pfeil lokalisiert und vom Spiel angenommen | aus dem Alignment |
| `absorbed` | verworfener MISS oder `darts_removed` | `NO_CHANGE` |
| `unbooked` | Pfeil lokalisiert, Visit aber schon voll | keins |

Anfangs standen nur `booked`-Frames in der Serie. Offline verkettete sie damit
gegen andere Referenzen als live: 72 von 542 Frames bekamen mit identischem Code
ein anderes Urteil, 79.3 % live gegen 74.5 % offline
([testrun1.md §8](../test/testrun1.md#8-testserien-vollständig-und-treu-schreiben)).
Aus demselben Grund wird der Frame erst nach `register_dart` eingeordnet — vorher
war nicht bekannt, ob der Dart angenommen wurde, und ein geschluckter vierter
Dart verschob die Labels der Serie um eins.

**Auch der Siegervisit.** Geschrieben wird sonst bei `next_player`, und ein
gewonnenes Spiel endet ohne. `recorder.settle_win` schreibt den Visit, sobald
`winner` gesetzt ist, und lässt ihn offen: nimmt ein Undo den Siegpfeil zurück,
wird dieselbe Serie beim nächsten Schreiben vollständig neu angelegt, samt
Löschen überzähliger Frames.

**Die Trigger-Episode je Frame.** Neben jedem `throwN_dartK.jpg` liegt, sofern
der Client sie mitgeschickt hat, `throwN_dartK_trigger.json`: die
Zusammenfassung aus `ThrowTriggerDto` plus eine `timeline` der letzten 40
verarbeiteten Frames des Triggers (≈ 2.4 s) — Zeit relativ zur Aufnahme,
Zustand *nach* dem Frame, aktive Zellen, Ambient-Pegel und die Indizes der
aktiven Zellen. Nur in Testläufen kommen `snapshots` dazu: das 160×90-Graubild
des Triggers und seine Änderungsmaske (ein Bit pro Pixel, beides base64) zu
den Momenten `arm`, `peak` und `capture`, zusammen etwa 60 KB pro Wurf.
`scripts/figures/trigger_figure.py` zeichnet daraus die Trigger-Abbildung. Damit
lässt sich offline nachzeichnen, wie der Wurf live erkannt wurde, ohne das Video
zu brauchen; gedacht für die Trigger-Abbildung der Arbeit und für die
Feldmessungen in [client-diff-verbesserungen.md](client-diff-verbesserungen.md).
`trigger_metrics_of` lässt die `timeline` aus, die Event-Metriken bleiben skalar.

**`ground_truth.txt` schreibt der Report, nicht der Server.** Welches Label zu
welchem Frame gehört, folgt erst aus dem Alignment — ein Frame ohne Partner in
der Wahrheit ist ein Phantom und bekommt `NO_CHANGE`, ein Wahrheits-Label ohne
Frame (`missed`) fällt weg. Passt die Zahl der `booked`-Frames nicht zu den
gebuchten Darts im Log (Undo über eine Visit-Grenze), bleibt die Serie
unmarkiert, statt verschobene Labels zu bekommen. Damit landen die Serien im
Format, das `scripts/detection/run_all.py` unverändert liest, und ein
korrigierter Visit wird ohne eine einzige Handmarkierung zum Testfall.

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
uv run python scripts/evaluation/report.py                       # wie die Seite (§7b)
uv run python scripts/evaluation/report.py --test-runs-only      # nur Testläufe
uv run python scripts/evaluation/report.py --include-unfinished  # auch Spiele ohne Sieger
uv run python scripts/evaluation/report.py <game-id>
```

Welche Spiele gelesen werden, entscheidet nicht das Skript, sondern
`services/accuracy.judged_games` — dieselbe Funktion wie für die Seite und den
Export (§7b). Ohne Schalter kommen Report, Seite und Export also auf dieselben
Spiele und dieselbe Kopfzahl.

Schreibt `accuracy.md` nach `testdata/evaluation/_report/` und je Spiel dessen
`ground_truth.txt` in den Bilderordner. Bewusst nicht nach `_results`: dorthin
schreibt `run_all.py`, wenn man es auf denselben Baum ansetzt, und es leert den
Ordner vor jedem Lauf.
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
- **Gebuchte MISS nach Lage der Spitze**: auf dem Board oder jenseits von
  225 mm. Ein „korrekter“ MISS jenseits des Boards ist verdächtig — das Alignment
  vergleicht nur Labels und paart ein MISS-Phantom mit einer von Hand
  eingetragenen Null ([testrun1.md §10](../test/testrun1.md#10-report-und-seite-angleichen)).
- Leer zurückgekommene Detektionen nach Failure-Typ (`no_change`,
  `alignment_failed`, `implausible_shape`) — das Maß für die Trigger-Qualität,
  zu der [client-diff-verbesserungen.md](client-diff-verbesserungen.md) gehört.
- Mismatch-Liste, nach Abstand aufsteigend.

### Export vom Pi

Report und Offline-Runner laufen lokal, die Daten entstehen auf dem Pi.
`scripts/evaluation/export.py` packt beides in ein Zip: `games.csv` und
`game_events.csv` im Format eines psql-Exports, dazu der Bilderordner unter
`testdata/evaluation/game_<id>/`. Entpackt ins Backend-Verzeichnis liegen die
Bilder damit dort, wo `run_all.py` und `run_debug.py` sie erwarten.

```bash
uv run python scripts/evaluation/export.py --list         # die ausgewählten Spiele
uv run python scripts/evaluation/export.py                # dieselben wie der Report, ein Zip
uv run python scripts/evaluation/export.py <game-id>      # nur dieses Spiel, ungefiltert
uv run python scripts/evaluation/export.py --per-game     # ein Zip je Spiel
```

Die Auswahl-Schalter `--test-runs-only` und `--include-unfinished` sind dieselben
wie beim Report (`scripts/evaluation/selection.py`). Ein Export und der Report
darüber lesen damit dieselben Spiele.

Geschrieben wird nach `testdata/_exports/`, auf dem Pi also nach
`/srv/dart-tracking/testdata/_exports/` — von dort per `scp` abholen. Auf dem Pi
im laufenden Container ausführen, der hat Datenbank und Bilder:

```bash
docker exec $(docker ps -qf name=backend) uv run python scripts/evaluation/export.py --list
```

---

## 7. Die Seite in der App

Der Report aus §6 beantwortet dieselbe Frage wie die Seite unter
`/account/evaluation`, nur mit einem Datenbank-Zugang und einem Terminal davor.
Beim Spielen ist genau das der Bruch: die Zahl entsteht am Abend, angesehen wird
sie am nächsten Tag. Die Seite zeigt sie sofort.

Referenz-Implementierung: `backend/src/app/api/features/evaluation/`,
Frontend `frontend/src/app/features/evaluation/`.

### 7a. Eine Rechnung, zwei Ausgaben

Skript und Seite dürfen nicht getrennt rechnen — zwei Quoten, die auseinander
laufen, sind schlimmer als keine. Die Rechnung liegt deshalb in
`domain/accuracy.py` und wird von beiden benutzt:

| Schicht | Was sie beisteuert |
|---|---|
| `domain/alignment.py` | Paarung getrackt ↔ akzeptiert (§3) |
| `domain/visit_replay.py` | Visits aus dem Event-Log |
| `domain/accuracy.py` | `judge` je Visit, `summarise` über eine Menge davon |
| `services/accuracy.py` | wählt die Spiele (`judged_games`), fasst je Spiel und gesamt zusammen |
| `scripts/evaluation/report.py` | rendert Markdown, schreibt `ground_truth.txt` |
| `dto/accuracy.py` + `evaluation.py` | dieselben Zahlen als JSON |

`report.py` behält, was nur dort Sinn ergibt: die Mismatch-Liste, die
Kohäsions-Tabelle, die Failure-Zählung und das Schreiben der Ground Truth. Die
Seite zeigt Kopfzahlen, Fehleraufschlüsselung, Fehler nach Feld und
Abstands-Buckets.

**Fehler nach Feld** (`field_errors`) teilt die geworfenen Pfeile nach dem Feld,
in dem sie laut Spielern steckten: Single, Double, Triple und Daneben. Der Bull
wird nach Multiplikator einsortiert wie in `Segment`: die 25 als Single, das
Bullseye als Double — so summieren sich die Zeilen weiter auf alle geworfenen
Pfeile, auf Kosten einer Double-Quote, die auch die Bullseye-Scheibe enthält. Je Feld zählen korrekt, falsch und verpasst;
Phantome fallen heraus, weil sie kein erwartetes Feld haben. Unter „falsch“
steht zusätzlich, wie viele im richtigen Sektor, aber im falschen Ring gebucht
wurden — das trennt einen Ring-Fehler (Kalibrierung radial, siehe
[kalibrierung.md §7](done/kalibrierung.md#7-offene-punkte)) von einem
Sektor-Fehler (Drahtseite, Rotation). Die Seite zeigt je Feld die geworfenen
Pfeile als Anteil aller geworfenen, darunter falsch und verpasst als
Anteil der Pfeile in diesem Feld; den Ring-Anteil zeigt nur der Report. Der Report („Accuracy per field“) führt dieselben Zählungen
plus die Quote korrekt / geworfen.

### 7b. Umfang: gesamt und pro Spiel

`GET /api/evaluation/accuracy` liefert beides in einer Antwort — die Totale und
jedes Spiel für sich, neuestes zuerst. Der Umschalter auf der Seite fragt den
Server also nicht erneut. Das ist tragbar, weil ein Spiel nur rund fünfzehn
Zahlen beiträgt; die Rechnung für die Totale ist ohnehin die Summe der
Einzelspiele, ein „nur die Liste"-Modus würde nichts sparen.

**Einbezogen sind alle abgeschlossenen, geloggten Spiele**, nicht nur die mit
gesetztem Testlauf-Schalter. Der Schalter aus §5 steuert das Ablegen der Bilder in
`testdata/evaluation/`, nicht die Messung: Events schreibt der Recorder immer.
Spiele ohne gefilmten Visit fallen heraus (`Visit.tracked`), sonst läsen sie
sich als Pfeile, die die Kamera nicht gesehen hat. Ebenso Spiele, deren gefilmte
Visits keinen einzigen gewerteten Pfeil ergeben — etwa eines, das nur einen
`no_change` hinterlassen hat. Es zählte sonst in „Games“ mit, ohne in einer
Zeile der Tabelle aufzutauchen.

**Nur `status = finished`.** Im Betrieb entstehen laufend Spiele, die nach ein,
zwei Pfeilen liegen bleiben — Kamera ausprobiert, Kalibrierung getestet. Sie
tragen kaum Judgements, tauchen aber als eigene Zeile in der Spielliste auf und
verrauschen die Einzelspiel-Ansicht. Filter im Repository
(`logged_games(finished_only=True)`), damit die Einschränkung in SQL passiert und
nicht erst nach dem Laden aller Logs. Anders als die Statistik
(`counts_in_statistics`, [persistenz.md §4.5](done/persistenz.md)) zählen
verlassene Spiele hier auch mit neun oder mehr Pfeilen nicht: ein
abgeschlossenes Spiel ist die sauberste Abgrenzung eines echten Durchlaufs.

**Report und Export wählen genauso.** Früher las `report.py` standardmäßig alle
Testläufe inklusive der nicht beendeten, die Seite alle beendeten Spiele — im
ersten Testlauf 15 gegen 11 Spiele und zwei verschiedene Kopfzahlen für dieselbe
Frage. Heute rufen alle drei `judged_games` auf; die Skripte weichen nur ab, wenn
ein Schalter es ausdrücklich verlangt.

### 7c. Warum eine Admin-Rolle

Die Seite berichtet über **fremde** Spiele — jedes Log in der Datenbank, egal
wer gespielt hat. Das ist der Unterschied zur Statistik-Seite, die nur das
eigene Konto auswertet, und der Grund für `users.role`
(`UserRole` = `user` | `admin`, Default `user`): `AdminUser` antwortet einem
angemeldeten Nicht-Admin mit **403**, nicht mit 404 — der Aufrufer ist bekannt,
die Route ist nur nicht seine. Im Frontend hängt derselbe Test am
`adminGuard` und daran, ob der Link auf der Konto-Seite überhaupt erscheint;
maßgeblich bleibt der Server.

Vergeben wird die Rolle in der Migration `f4a1c7d2e903`, die eine Adresse auf
`admin` setzt. Weitere Admins per SQL — ein Konto zu befördern ist kein
Vorgang, der eine Oberfläche braucht.

---

## 8. Tracker-Version und Kamerawinkel

Zwei Dinge, nach denen sich die Genauigkeit aufschlüsseln lassen soll: *mit
welchem Code* gespielt wurde, und *aus welchem Winkel* die Kamera auf die
Scheibe sah.

### Version

`games.tracker_version`, gesetzt beim Anlegen des Spiels: die GitLab-
Pipelinenummer (`CI_PIPELINE_IID`), die die Deploy-Pipeline als Build-Arg
`APP_BUILD` an das Backend-Image übergibt und `Settings.app_build` liest. Als
Build-Arg und nicht als Laufzeit-Variable, damit die Nummer am Image klebt und
nicht davon abhängt, mit welcher Umgebung `docker compose up` zuletzt lief.
Welcher Commit dahintersteht, zeigt die Pipeline in GitLab — die Nummer ist pro
Projekt eindeutig, der Commit wird deshalb nicht mitgespeichert.

Das Frontend bekommt dieselbe `APP_BUILD` aus derselben Pipeline — eine Zahl
beschreibt also Trigger im Browser und CV-Pipeline gemeinsam. Lokal und bei
allen Spielen vor dieser Spalte ist sie leer, Report und Seite zeigen dann
`unknown` bzw. „unbekannt“.

Bewusst am Spiel, nicht an jedem Event: ein Deploy mitten im Spiel würde die
Würfe danach falsch zuordnen, kommt an einem Testabend aber nicht vor.

### Kamerawinkel

Aus der Homographie jeder Kalibrierung, ohne zusätzliche Messung
(`calibration/domain/camera_angle.py`):

1. `H⁻¹` (Board → Bild) auf die Bildmitte als Hauptpunkt verschieben.
2. Die Brennweite schätzen: `H = K·[r₁ r₂ t]` mit `K = diag(f, f, 1)`, und
   `r₁`, `r₂` müssen orthogonal und gleich lang sein. Zwei Gleichungen, eine
   Unbekannte (`f²`), per Least Squares.
3. `r₁`, `r₂`, `t` herausrechnen, `R` orthonormalisieren, Kameraposition
   `C = −Rᵀt` in Board-Millimetern.
4. Winkel aus `C`: **Neigung** gegen die Board-Normale, **horizontal**
   `atan2(Cₓ, C_z)` (negativ = links vom Board, vom Abwurf aus gesehen),
   **vertikal** `atan2(C_y, C_z)` (negativ = unterhalb des Bulls).

Fast frontal ist Schritt 2 entartet (die Tiefenanteile von `H` gehen gegen
null). Liegt die Schätzung außerhalb von 0.5 – 3 × der langen Bildkante, gilt
stattdessen eine typische Handy-Hauptkamera (26 mm KB-äquivalent). Die Winkel
sind dort ohnehin klein, der Fehler bleibt es auch.

Geloggt wird jede erfolgreiche Kalibrierung der **scorenden** Kamera als
`calibrated`-Event (Winkel plus `focal_px` in `metrics`). Pro Spiel gilt der
**Median** darüber (`camera_angle_of`): die Kamera steht fest, die
Kalibrierungen streuen um ±0.5°, und eine einzelne verzogene fällt so nicht ins
Gewicht. Die Historie bleibt im Log — springt die Pose zwischen zwei
Kalibrierungen, obwohl niemand die Kamera angefasst hat, war eine davon schief.
Das ist ein Ansatzpunkt für die fehlende Selbstprüfung aus
[kalibrierung.md §7](done/kalibrierung.md#7-offene-punkte).

**Validierung am Testset** (`throw*_base.jpg` je Detektions-Setup, Client-Kette):

| Setup | Neigung | horizontal | vertikal | Accuracy offline |
|---|---|---|---|---|
| pz_setup1 | 13° | +8° | −11° | 73 % |
| tz_setup1 | 15° | +4° | −15° | 87 % |
| pz_setup3 | 23° | +1° | −23° | 93 % |
| cc_setup1 | 27° | −1° | −27° | 80 % |
| pz-light_setup3 | 30° | −1° | −30° | 87 % |
| pz_setup4 | 31° | −1° | −31° | 87 % |
| tz_setup3 | 31° | +23° | −23° | 93 % |
| cc_setup2 | 32° | −19° | −28° | 93 % |
| fh_setup2 | 35° | −2° | −35° | 80 % |
| pz_setup2 | 36° | −30° | −24° | 73 % |
| tz_setup2 | 36° | −25° | −30° | 67 % |
| tz_setup4 | 40° | −28° | −33° | 80 % |
| fh_setup1 | 40° | +20° | −37° | 53 % |
| pz-light_setup2 | 46° | +43° | −25° | 90 % |
| tz_setup5 | 54° | −48° | −39° | 73 % |
| pz-light_setup1 | 55° | −50° | −41° | 80 % |

- **Neigung robust.** Die grobe Näherung über das Achsenverhältnis der
  gefitteten Ellipse (`cos θ ≈ b/a`) liegt überall innerhalb von 1 – 3° an der
  vollen Posenschätzung, über die Basisbilder eines Setups streut sie ±0.5°.
- **Aufteilung plausibel.** `left_near`/`right_near` landen auf der richtigen
  Seite, `pz-light_setup1` (das „Stativ weit seitlich“ aus
  [kalibrierung.md §2.5](done/kalibrierung.md#25-zuordnung-zu-board-winkeln))
  ist das steilste Setup. Streuung innerhalb eines Setups ±1 – 2°.
- **Brennweite nötig.** Mit fester Standardbrennweite statt Schätzung liegt die
  Aufteilung um 5 – 8° daneben. Die Testfotos tragen keine EXIF-Daten; wo doch
  (zwei Bilder), passt die Schätzung auf 5 – 20 %.
- **Kein Abstand, keine Höhe in mm.** `C` selbst ist bei schräger Kamera auf
  etwa ±5 % stabil, fast frontal springt der Abstand um Dezimeter
  (`tz_setup1`: 2.0 – 2.7 m). Gespeichert werden deshalb nur Winkel.
- **Kein Zusammenhang mit der Accuracy erkennbar** — bei 15 – 30 Würfen je Setup
  sind ±10 % aber Rauschen. Genau dafür ist die Live-Aufzeichnung da.

Objektivverzeichnung bleibt unmodelliert (wie in der Kalibrierung selbst); für
Winkel in Grad-Genauigkeit reicht das.

### Wo es auftaucht

- **Report:** Spalten Version, Neigung, horizontal, vertikal in „Per game“, dazu
  Quoten je Version, je Neigungsband (< 20°, 20 – 35°, 35 – 50°, ≥ 50°) und je
  Seite/Höhe (jenseits von ±15° links/rechts bzw. unter/über dem Bull).
- **Seite:** bei einem einzelnen Spiel ein Abschnitt „Aufnahme“ mit Version und
  Winkeln.
- **Export:** über `games.csv` und die `calibrated`-Zeilen in `game_events.csv`.

---

## 9. Offene Punkte

- **Mehrfach-Trigger ohne Wurf bleiben ungezählt.** Löst die Kamera ohne Wurf
  aus und findet nichts, entsteht gar kein Judgement — weder auf der
  Behauptungs- noch auf der Wahrheitsseite steht etwas. Diese Fälle erscheinen
  nur in der Failure-Tabelle. Ob Trigger-Qualität in die Genauigkeitszahl
  gehört, ist bewusst offen; sie steckt heute in
  [client-diff-verbesserungen.md](client-diff-verbesserungen.md).
- **Kein Setup-Begriff jenseits des Winkels.** Offline gruppiert die Auswertung
  nach Board und Setup (`pz_setup1`); live trennt §8 inzwischen nach
  Kamerawinkel, Board und Licht aber nicht. Solange an einem Board gespielt
  wird, reicht das.
- **Latenz ungemessen.** Die Zeitstempel des Logs geben den Abstand zwischen
  Trigger und Buchung her, ausgewertet wird er noch nicht.
- **`FrameBuffer` wird nie geleert.** Prozesslokal und an kein Spielende
  gebunden, wie `detection_store` auch — rund ein Megabyte je Spiel, das bis zum
  Neustart liegen bleibt.
- **Doppelkamera.** Nur die scorende Kamera wird gemessen. Die zweite liefert
  bereits die unabhängige Zweitbeobachtung, aus der eine Fusion gebaut würde
  ([multi-device.md §5](done/multi-device.md)); ihre Trefferquote gegen dieselbe
  Wahrheit zu messen wäre der nächste Schritt.
