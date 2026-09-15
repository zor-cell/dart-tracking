# Testdaten-Aufnahme im laufenden Spiel

Arbeitsplan für ein Feature, das während eines normalen Spiels beschriftete
Testdaten für die Detektions-Pipeline produziert: der Server legt die Frames
jedes Wurfs im Format von `backend/testdata/detection/` ab, der Spieler
korrigiert im Vorbeigehen, was falsch erkannt wurde, und das korrigierte Segment
landet als Ground Truth daneben.

Gegenstück zu [erkennung-verbesserungen.md](../erkennung-verbesserungen.md) und
[client-diff-verbesserungen.md](../client-diff-verbesserungen.md): die beiden planen
*Änderungen an der Pipeline*, dieses Dokument plant die **Datenbasis**, an der
solche Änderungen überhaupt gemessen werden können.

---

## 1. Warum

Das Testset hat 285 Paare über fünf Boards und 16 Setups
([erkennung.md §6](erkennung.md#6-stand-der-messungen)). Jedes davon ist von Hand
entstanden: Fotoserie aufnehmen, auf den Rechner ziehen, Ordner benennen, und die
`ground_truth.txt` **nachträglich gegen die Videos** beschriften. Der letzte
Schritt ist der teure, und er ist auch der fehleranfälligste — ein Segment aus
einem Standbild abzulesen ist genau das Problem, das die Arbeit lösen will.

Die entscheidende Beobachtung: **im Moment des Wurfs ist die Wahrheit gratis.**
Der Spieler steht vor dem Board und sieht, wo der Pfeil steckt. Alles, was fehlt,
ist ein Weg, diese Information abzugreifen, bevor sie verloren geht.

Zwei Größenordnungen Unterschied im Aufwand: eine gespielte Session mit 30 Visits
sind 90 beschriftete Paare — ein Drittel des heutigen Testsets, an einem Abend,
ohne Nacharbeit. Damit werden auch die Aussagen aus
[erkennung.md §6](erkennung.md#6-stand-der-messungen) belastbarer, die derzeit
teils auf Board-Aufschlüsselungen mit 20–30 Paaren beruhen.

Nebeneffekt, der eigenständig zählt: die Korrektur ist auch für das *Spiel*
richtig. Ein falsch erkannter Pfeil wird heute falsch gebucht, und die einzige
Rettung ist Undo plus manuelle Eingabe. Dieselbe Geste, die die Ground Truth
setzt, kann den gebuchten Dart korrigieren.

---

## 2. Kernbefund: nichts muss ans Handy zurück

In [`_handle_throw_frame`](../../../backend/src/app/api/core/socket/socket.py) liegt
zum Zeitpunkt der Detektion bereits alles vor:

| Was | Woher |
|---|---|
| das eingehende JPEG | `frame.image`, base64 — schon vom Client auf 1280 px / q85 gebracht |
| der Referenz-Frame | `detection_store.get(game_id, client_id)` |
| die Kalibrierung | `calibration_store.get(game_id, client_id)` |
| das erkannte Segment | `outcome.segment.label` |

Der Server schreibt die Bilder also selbst. Das Handy schickt nur einen String
hinterher, wenn das Segment nicht stimmte. Kein Bild-Rücktransport, kein
Upload-Endpoint, keine zweite Kopie der Frames im Browser-Speicher.

Das entwertet zugleich den mühsamen Weg „Handykamera an den PC koppeln": nötig
war der nur, weil die Bilder sonst nicht dorthin kamen, wo die Ground Truth
entsteht. Mit serverseitiger Aufnahme spielt man einfach am realen Pi-Setup.

---

## 3. Status

| # | Schritt | Ort | Aufwand | Status |
|---|---|---|---|---|
| 1 | [Aufnahme-Store und Ablage](#5-aufnahme-was-auf-die-platte-geht) | Server | M | offen |
| 2 | [`recordingId` im Detection-Result](#6-der-weg-des-labels) | Server | S | offen |
| 3 | [`label_dart`-Command](#6-der-weg-des-labels) | beide | S | offen |
| 4 | [Setting: Aufnahme + Session-Name](#7-bedienung) | Frontend | S | offen |
| 5 | [Korrektur-UI am Visit-Ende](#7-bedienung) | Frontend | M | offen |
| 6 | [Klickbares Board als Segment-Picker](#7-bedienung) | Frontend | S | offen |
| 7 | [Volume + `raw`-Marker für `run_all.py`](#8-ablage-und-transport-vom-rpi5) | Infra | S | offen |
| 8 | [Zip-Export-Endpoint](#8-ablage-und-transport-vom-rpi5) | Server | S | offen, optional |

Reihenfolge: 1–3 zuerst und mit einem hart verdrahteten Session-Namen testen —
danach steht die Aufnahme und die UI ist nur noch Komfort. 7 muss vor der ersten
Aufnahme am Pi stehen, sonst sind die Daten beim nächsten Rebuild weg (§8).

---

## 4. Was aufgenommen wird — Begriffe

Das bestehende Layout (siehe `scripts/detection/run_all.py`):

```
<session>/
  throw1_base.jpg     leeres Board
  throw1_dart1.jpg    nach dem ersten Pfeil
  throw1_dart2.jpg
  throw1_dart3.jpg
  throw2_base.jpg
  …
  ground_truth.txt    "throw1_dart1 S5" je Zeile
```

`run_all.py` verkettet aufeinanderfolgende Dateien einer Serie
(`base→dart1→dart2→dart3`) und differenziert jedes Paar — dieselbe Kette wie
live. Eine **Serie entspricht einem Visit**, und diese Grenze existiert im System
bereits: `next_player` löst eine Rekalibrierung aus
([socket.py](../../../backend/src/app/api/core/socket/socket.py),
`_request_calibration`), und der Kalibrierungs-Frame *ist* das `base` des nächsten
Visits.

Die Aufnahme muss also keine eigene Segmentierung erfinden. Sie hängt sich an
zwei Ereignisse, die es schon gibt:

- **erfolgreiche Kalibrierung** → neue Serie beginnt, dieser Frame ist ihr `base`
- **erfolgreiche Detektion** → nächster `dartM` der laufenden Serie

---

## 5. Aufnahme: was auf die Platte geht

### Rohe Bytes, nicht der ausgerichtete Frame

Geschrieben wird das **empfangene JPEG unverändert**, nicht `trace.aligned`.
`run_all.py` leitet die Registrierung selbst wieder her; ein bereits gewarptes
Bild würde zweimal ausgerichtet und wäre als Testdatum wertlos.

Das gilt auch für das `base`: `detection_store` hält nach der Kalibrierung den
*dekodierten* Frame und überschreibt ihn später mit der ausgerichteten Kopie. Die
Aufnahme braucht deshalb ihre eigene Ablage der **rohen Kalibrierungs-Bytes**,
die erst geschrieben wird, wenn der erste Pfeil der Serie tatsächlich fällt —
sonst sammelt jede erfolglose Kalibrierung ein verwaistes `base` an.

### Der Fall, der die Kette zerstört: nicht erkannte Würfe

Der wichtigste Punkt dieses Plans, und beim Entwurf zunächst übersehen.

Live rollt der Referenz-Frame **nur bei erfolgreicher Detektion** weiter — bei
`NO_CHANGE` kehrt `_handle_throw_frame` vorher zurück, die Referenz bleibt stehen.
Der nächste Wurf wird also gegen den *vorletzten* Frame differenziert.

Auf der Platte reproduziert man das exakt, indem man nicht erkannte Frames
**gar nicht in die Kette schreibt**: Dateien `dart1`, `dart2`, wobei `dart2` der
dritte geworfene Pfeil ist — `run_all.py` verkettet `dart1→dart2` und trifft damit
dieselbe Paarung wie live. Schriebe man den abgelehnten Frame als eigenen
Kettenglied mit, entstünde ein Paar, das es live nie gab.

Wegwerfen will man ihn trotzdem nicht: ein Wurf, den der Detektor nicht sieht,
ist ein Falsch-Negativ und damit genau das Material, das
[client-diff-verbesserungen.md §6](../client-diff-verbesserungen.md) („der
abgefallene Pfeil ist eine Null") braucht. Also:

```
<session>/_rejected/throw3_after-dart1_no-change.jpg
```

`_EXCLUDED_DIRS` in `backend/scripts/common.py` bekommt `_rejected` dazu (eine
Zeile), damit ein Batch-Lauf diese Bilder nicht als Eingaben einliest.

`INVALID_IMAGE` und `NOT_CALIBRATED` entstehen vor dem Detektor und werden
komplett ignoriert — dort gibt es kein verwertbares Bild.

### Serien-Nummerierung

Der Zähler darf nicht bei `throw1` beginnen, wenn im Zielordner schon Serien
liegen (zweite Session, gleicher Name, oder ein Neustart des Backends — die
Stores sind prozesslokal). Beim Anlegen einer Session einmal den Ordner globben
und hinter der höchsten vorhandenen Nummer weiterzählen.

### Mehrere Kameras

Ein Wurf, zwei Blickwinkel, **ein** Label — das ist mehr wert als die Aufnahme
einer einzelnen Kamera, und kostet nichts extra. Die Scoring-Kamera
(`scoring_camera_store`) schreibt nach `<session>/`, jede weitere nach
`<session>/cam2/` usw.; `run_all.py` walkt rekursiv und hält die Serien über den
relativen Pfad auseinander. Jeder Ordner bekommt seine eigene `ground_truth.txt`
mit denselben Labels.

Die Sonderrolle der Scoring-Kamera ist hier nur Kosmetik: sie hält den Normalfall
(eine Kamera) flach statt in einem sinnlosen `cam1/`.

### Ort im Code

Nicht in `socket.py`. Die Datei ist mit den Debug-Dumps schon überladen (steht so
in [todo.md](../../status/todo.md): *„socket.py cleanen, die debug writes wirken dort fehl
am platz"*), und Aufnahme ist ein Feature mit eigenem Zustand. Also:

```
backend/src/app/api/features/recording/
  domain/recording_session.py    Serien-/Dart-Zähler, Ordner, pending base
  dto/command/label_dart.py      LabelDartDto
  services/recording_store.py    Session je (game, client)
  services/recorder.py           schreibt Frames und ground_truth.txt
  recordings.py                  optionaler Zip-Export-Router (§8)
```

In `socket.py` bleiben zwei Aufrufe stehen, je einer in
`_handle_calibration_frame` und `_handle_throw_frame`, plus der neue Command-Zweig
im `match`.

---

## 6. Der Weg des Labels

Der Server hängt dem `detection_result` eine **`recordingId`** an — den relativen
Pfad des gerade geschriebenen Frames ohne Endung:

```jsonc
{ "type": "detection_result", "success": true, "segment": "S12",
  "recordingId": "pz_setup5/throw3_dart1" }
```

Der Client hält sie für die laufende Runde und echot sie zurück, wenn korrigiert
wird:

```jsonc
{ "type": "label_dart", "recordingId": "pz_setup5/throw3_dart1", "segment": "T20" }
```

Der Server hängt `throw3_dart1 T20` an die `ground_truth.txt` des Ordners, der in
der Id steckt. Damit muss der Client das Datei-Layout **nicht kennen** — er
behandelt die Id als opaken Schlüssel, und die Ordnerstruktur bleibt eine reine
Server-Angelegenheit.

`recordingId` ist optional und fehlt, wenn nicht aufgenommen wird; das Feld
allein schaltet die Korrektur-UI frei.

**Bestätigte Erkennungen brauchen ebenfalls eine Zeile.** Ein Ordner ohne
`ground_truth.txt`-Eintrag zählt in `run_all.py` gar nicht mit, also schreibt der
Client am Visit-Ende für *alle* drei Darts ein Label — die unveränderten mit dem
erkannten Segment. Das ist der Unterschied zwischen „hat gestimmt" und „wurde nie
angeschaut", und `--truth-template` kann ihn nachträglich nicht rekonstruieren.

Das Format ist bereits round-trip-fähig: `Segment.label` und
`segment_from_label` in
[`board_geometry.py`](../../../backend/src/app/api/features/calibration/domain/board_geometry.py)
sind zueinander invers. Der Server validiert das eingehende Label darüber und
verwirft, was sich nicht parsen lässt.

### Nachträgliche Korrektur

Eine `ground_truth.txt` wird angehängt, nicht neu geschrieben. Zweimal dasselbe
`recordingId` zu labeln (Korrektur der Korrektur) hinterlässt zwei Zeilen. Der
Leser in `run_all.py` müsste dann „letzte Zeile gewinnt" implementieren — oder
der Server liest die Datei vor dem Schreiben und ersetzt die Zeile. Letzteres ist
sauberer und bei diesen Dateigrößen ohne Belang.

---

## 7. Bedienung

### Setting

Zwei Felder in [`app-settings.ts`](../../../frontend/src/app/features/settings/models/app-settings.ts),
im Debug-Abschnitt der Settings-Seite:

- `recordTestData: boolean`
- `recordingSession: string` — der Ordnername, z.B. `pz_setup5`. Konvention ist
  `<board>_<setup>`, und die kann der Server nicht raten.

Beides geht als Feld am `detection_frame`/`calibration_frame` mit, so wie das
`debug`-Flag heute schon. Kein eigener „Session starten"-Command: das Flag am
Frame ist zustandslos und überlebt jeden Reconnect.

### Korrektur — Variante B (Empfehlung)

Bei aktivem `confirmThrowEnabled` gibt es am Visit-Ende bereits einen
Bestätigungs-Schritt ([game.component.html](../../../frontend/src/app/features/game/components/game/game.component.html),
`turn__confirm`). Dort werden die drei Darts der Runde antippbar: Tap öffnet den
Segment-Picker, der Bestätigen-Button schreibt alle drei Labels und schaltet wie
gehabt weiter.

**Warum nicht das Popup nach jedem Wurf** (die ursprüngliche Idee): drei
Unterbrechungen pro Visit statt einer, und zwar jeweils in dem Moment, in dem der
Spieler den nächsten Pfeil in der Hand hat. Die Bestätigung am Ende existiert
ohnehin, liegt zeitlich richtig (alle drei Pfeile stecken noch im Board und sind
ablesbar) und braucht keinen neuen Interaktionspunkt.

**Kopplung an `confirmThrowEnabled`.** Ohne Bestätigung feuert `next_player`
direkt nach dem dritten Dart, die Rekalibrierung sieht ein Board mit drei Pfeilen,
und das aufgenommene `base` des nächsten Visits ist unbrauchbar — der bekannte
Punkt aus [erkennung.md §7](erkennung.md#7-offene-punkte). Aufnahme erzwingt
deshalb den Bestätigungs-Modus, oder das Setting warnt sichtbar.

### Segment-Picker

Das [`virtual-board`](../../../frontend/src/app/features/game/components/virtual-board/virtual-board.component.ts)
klickbar machen: es zeichnet das Board bereits und kennt die Geometrie über
`board-geometry.ts`. Du tippst hin, wo der Pfeil wirklich steckt — schneller und
weniger fehleranfällig als ein S/D/T-Keypad, weil die Eingabe dieselbe räumliche
Form hat wie die Wahrnehmung.

Zusätzlich ein `MISS`-Knopf, denn außerhalb des Doubles gibt es nichts zu tippen.

### Score-Korrektur als Mitnahme

Ein korrigiertes Label heißt fast immer auch: falsch gebucht. `undo` und
`register_dart` existieren als Commands, die Korrektur kann sie direkt mit
auslösen. Bewusst als eigener Schritt notiert, weil es das Feature vom
Debug-Werkzeug zum Spiel-Feature macht und entsprechend getestet werden will.

---

## 8. Ablage und Transport vom RPi5

**Befund: [`compose.yaml`](../../../compose.yaml) mountet für den Backend-Service
nichts.** Aufgenommene Testdaten lägen im Container-Dateisystem und wären beim
nächsten `docker compose up --build` verloren. Das ist Voraussetzung, nicht
Komfort:

```yaml
backend:
  volumes:
    - ./backend/testdata:/app/testdata
```

Danach zwei Wege an die Bilder:

1. **`rsync`/`scp` vom Pi.** Null Code. Reicht für den Anfang.
2. **Zip-Export**: `GET /api/recordings/{session}.zip` mit `zipfile` +
   `FileResponse`, dazu ein Button auf der Settings-Seite. Session fertig →
   Button → Zip am Laptop, ohne SSH. ~40 Zeilen, lohnt sich ab der zweiten
   Session.

Platzbedarf ist kein Thema: rund 1,5 MB pro Visit (4 Frames), also ~50 MB für
eine Session mit 30 Visits.

### Doppelte JPEG-Kompression

Die aufgenommenen Frames sind bereits client-kodiert (1280 px, q85). `run_all.py`
schickt Eingaben standardmäßig durch `as_client_would_send` und würde sie ein
**zweites Mal** durch q85 jagen — das Testdatum wäre dann schlechter als das, was
live ankommt.

`load_image` in `scripts/common.py` hat dafür schon ein `raw`-Flag. Statt sich
`--raw` je Ordner zu merken: eine Marker-Datei (`.client-encoded`) im
aufgenommenen Ordner, die den Re-Encode automatisch überspringt. Fünf Zeilen, und
der Ordner trägt die Information selbst — kein Wissen, das an einer
Kommandozeile hängt.

---

## 9. Verworfene Alternativen

### 9.1 Frames vom Client hochladen

*Idee:* Der Browser hält die gesendeten Frames und lädt sie am Visit-Ende
zusammen mit den Labels hoch.

*Warum verworfen:* Der Server hat die Bilder bereits (§2). Ein Upload wäre eine
zweite Kopie durchs Netz, ein zweiter Encoder-Durchlauf und ein neuer Endpoint —
für Daten, die schon am Ziel liegen. Auf dem Handy kämen ein paar MB
Speicherhaltung pro Visit dazu.

### 9.2 Nachträglich mit `--truth-template` beschriften

*Idee:* Nur aufnehmen, Labels später aus den Detektionen bootstrappen und die
falschen von Hand ausbessern.

*Warum verworfen:* Das ist der heutige Zustand mit weniger Schritten, nicht ein
anderer Zustand. Die teure Arbeit — aus einem Standbild ablesen, wo der Pfeil
steckt — bleibt vollständig erhalten, und sie bleibt genau dort fehleranfällig,
wo die Pipeline es auch ist: bei knappen Triple/Double-Entscheidungen sieht man
es dem Foto nicht besser an als dem Detektor. Der Live-Moment ist die einzige
Gelegenheit, an der die Wahrheit ohne Interpretation vorliegt.

*Bleibt nützlich* als Fallback für Serien, die ohne aktive Aufnahme entstanden
sind.

### 9.3 Nicht erkannte Frames in die Kette schreiben

*Idee:* Jeden getriggerten Frame als Kettenglied ablegen, unabhängig vom Ausgang.

*Warum verworfen:* Erzeugt Paare, die live nie existierten — die Referenz rollt
bei einer Fehlschlag-Antwort nicht weiter (§5). Die Frames wandern stattdessen
nach `_rejected/` und bleiben für die Trigger-Arbeit erhalten.

---

## 10. Aufwand

| Teil | Umfang |
|---|---|
| Backend `features/recording/` (Session-Domain, Store, Recorder, `label_dart`) | ~250–350 Zeilen |
| Backend: zwei Hooks in `socket.py`, `recordingId` im `DetectionResultDto` | ~30 Zeilen |
| Frontend: Setting (Toggle + Session-Name) | ~40 Zeilen |
| Frontend: Recording-Service (Runde puffern, Labels senden) + Korrektur-UI | ~250–350 Zeilen |
| Frontend: `virtual-board` als Picker | ~60 Zeilen |
| Infra: Volume, `_rejected` in `_EXCLUDED_DIRS`, `.client-encoded`-Marker | ~10 Zeilen |

**Realistisch 1–1,5 Tage** inklusive einer echten Test-Session am Pi-Setup. Der
Zip-Export (§8) sind weitere ~2 Stunden und kann jederzeit nachkommen.

Die eigentliche Verifikation ist nicht „läuft durch", sondern: eine aufgenommene
Session durch `scripts/detection/run_all.py` schicken und prüfen, dass die
Accuracy auf diesen Paaren in derselben Größenordnung liegt wie live beobachtet.
Weicht sie ab, stimmt etwas an der Kette (§5) oder an der Kodierung (§8) nicht —
und dann sind alle so erzeugten Daten falsch, nicht nur einzelne.

---

## 11. Offene Punkte

- **Board-Bewegung während einer Session.** Wird die Kamera verschoben, gehören
  die folgenden Serien in ein anderes Setup. Aktuell müsste der Session-Name von
  Hand geändert werden. `alignment_shift_px` liegt vor
  ([kalibrierung.md §7](kalibrierung.md#7-offene-punkte)) und könnte das erkennen
   — dasselbe fehlende Stück wie bei der Re-Kalibrierung.
- **Wie viel Korrektur ist zu viel Korrektur?** Wenn der Spieler das Label setzt,
  nachdem er die Erkennung gesehen hat, besteht ein Ankereffekt — bei einem
  knappen Triple ist „passt schon" bequemer als nachzumessen. Für die 5-mm-Klasse
  aus [erkennung.md §6](erkennung.md#was-den-restfehler-ausmacht) ist das genau
  die Population, um die es geht. Möglicher Ausweg: das erkannte Segment im
  Korrektur-Schritt erst *nach* der Eingabe zeigen. Kostet Tempo, und ob es sich
  lohnt, ist ungeprüft.
- **Datenschutz/Ballast.** Aufnahmen enthalten den Raum im Hintergrund. Für eine
  Veröffentlichung des Testsets als Teil der Arbeit relevant, sonst nicht.
- **Aufnahme ohne Spiel.** Ein reiner Aufnahmemodus (kein Score, nur werfen und
  labeln) wäre für gezielte Setup-Serien schneller als ein 501er. Erst sinnvoll,
  wenn die Aufnahme im Spiel steht.
