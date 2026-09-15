# Testlauf 1: Befunde und Anpassungsplan

Auswertung aller bisher aufgezeichneten Testspiele (Export vom 15.09.,
`testdata/evaluation/_exports/export_20260915-110036`, Report in
`testdata/evaluation/_report_prod/accuracy.md`) und der Plan, was daraus
angepasst wird. Gegenstück zu [auswertung.md](../feature/auswertung.md), das das
Messinstrument beschreibt; hier geht es um das, was es gemessen hat.

---

## Datengrundlage

- 15 gefilmte Spiele, 217 Visits, 620 geworfene Pfeile, 1730 leer
  zurückgekommene Detektionen, 735 Bilder.
- Kopfzahl: **478 / 620 korrekt (77.1 %)**, 38.7 % der Visits ohne Korrektur.
  Mit dem Replay- und Alignment-Code aus `features/evaluation/domain/` exakt
  reproduziert.
- Die Spiele liegen auf **fünf Code-Ständen**. Aus Commit-Zeiten und den im Log
  vorhandenen Feldern erschlossen:

| Stand | Spiele | Was schon aktiv war |
|---|---|---|
| A 12.09. abends | `09725`, `0974d`, `09750` | MISS-Grenze < 400 mm² (ab `0974d` auch das Weiterrollen) |
| B 13.09. vormittags | `09a30`, `09a34` | + Trigger-Metriken |
| C 13.09. mittags | `09a65`, `09ace` | + Ruhe nach Timeout, `darts_removed` |
| D 14.09. | `0a051`, `0a062`, `0a063`, `0a06c`, `0a0a1` | + Ansage, Kameraansicht |
| E 15.09. | `0a49c`, `0a4a4`, `0a4ad` | + `dart_removed` |

Befunde, die nur in Stand A auftreten, sind unten nicht mehr aufgeführt. Die
Visits ohne Korrektur stiegen von 2/16 und 2/17 (A) auf 8/16 und 13/26 (E).

**Wie sich die Fehler zusammensetzen:**

- **missed (49):** 23 davon sind von Hand eingetragene Nullen (Abpraller,
  Surround) und damit per Konstruktion `missed` ([auswertung.md §3a](../feature/auswertung.md#3a-die-gelesene-null-zählt-nicht)).
  Echt verpasst wurden 26 punktende Pfeile, 8 davon im ersten Spiel.
- **wrong (93):** 34 falscher Sektor, 27 falscher Ring, 32 MISS gegen Punktwert.
  39 liegen unter 5 mm (Drahtseite, Präzisionsgrenze).
- **phantom (48):** siehe Schritte 1, 3 und 4.

---

## Status

| # | Schritt | Ort | Aufwand | Status |
|---|---|---|---|---|
| 1 | [Rekalibrierung erst auf leerem Board](#1-rekalibrierung-erst-auf-leerem-board) | Server + Client | M | offen |
| 2 | [Gezogene Pfeile vor der Größenprüfung erkennen](#2-gezogene-pfeile-vor-der-größenprüfung-erkennen) | Server | S | offen |
| 3 | [Ring-Innenkanten nachmessen](#3-ring-innenkanten-nachmessen) | Server | S–M | offen, braucht Lineal |
| 4 | [Orientierung bei steiler Kamera](#4-orientierung-bei-steiler-kamera) | Server | M | offen |
| 5 | [Mindestfläche für punktende Pfeile](#5-mindestfläche-für-punktende-pfeile) | Server | S | offen |
| 6 | [Zu lange Blobs neu fusionieren statt verwerfen](#6-zu-lange-blobs-neu-fusionieren-statt-verwerfen) | Server | M | offen |
| 7 | [Rekalibrierung bei Kameraversatz](#7-rekalibrierung-bei-kameraversatz) | Server | S | offen |
| 8 | [Testserien vollständig und treu schreiben](#8-testserien-vollständig-und-treu-schreiben) | Server | S | offen |
| 9 | [Kalibrierungen ins Event-Log](#9-kalibrierungen-ins-event-log) | Server | S | offen |
| 10 | [Report und Seite angleichen](#10-report-und-seite-angleichen) | Skript | S | offen |
| 11 | [Client-Trigger: Schritt 2 und 4 zurückstellen](#11-client-trigger-schritt-2-und-4-zurückstellen) | Doku | – | Entscheidung |

**Reihenfolge:** 8 zuerst, weil jede weitere Messung auf den Serien aufbaut.
Dann 1 und 2 (größter struktureller Schaden), dann 3 (größter Hebel auf die
Quote pro Aufwand), dann 4–7.

**Messdisziplin.** Server-Schritte werden wie bisher mit
`scripts/detection/run_all.py` gegen den kuratierten Testsatz (285 Paare) belegt
*und* gegen die aufgezeichneten Serien. Die Serien sind dafür erst nach Schritt 8
brauchbar (siehe dort).

---

## 1. Rekalibrierung erst auf leerem Board

**Befund.** `_request_calibration` feuert direkt bei `next_player`. Wird der
Wechsel bestätigt, bevor die Pfeile gezogen sind, kalibriert die Kamera auf ein
volles Board — und dieses Bild wird zugleich Referenz *und* „leeres Board“ für
`changed_from_empty`.

- In mindestens **11 von 186 Basisbildern** stecken noch Pfeile (gezählt nur
  blaue Flights, also Untergrenze): `09750` throw6/9, `09a65` throw2/5, `0a051`
  throw2, `0a49c` throw2/8, `0a4ad` throw13/16/17/18.
- Genau dort liegen **alle fünf MISS-Phantome über 3000 mm²** (Spitze bei
  r 250–313 mm, `trigger_timed_out` 1, Spieler vor dem Board) und das doppelt
  gebuchte S20 in `09750` throw6.
- In den ersten 5 s nach dem Wechsel stehen 8 Phantome gegen 6 korrekte Pfeile
  und 281 `no_change`.

**Fix.** Die Rekalibrierung wird bei `next_player` nur *vorgemerkt* und erst
ausgelöst, wenn die Kamera nach dem Wechsel eine Bewegungsepisode gesehen hat und
danach wieder ruhig ist (Ziehen → Zurückgehen → Ruhe). Solange sie aussteht,
sendet der Client keine `detection_frame`s. Recall kostet das nicht: ein Pfeil,
der in diesem Fenster geworfen wird, steckt nach der Kalibrierung noch und wird
gegen die neue Referenz gefunden — allerdings nur, wenn die Kalibrierung *vor*
dem ersten Wurf kommt. Deshalb zusätzlich:

- Das Kalibrierungsbild gegen die letzte Referenz differenzieren. Sieht es noch
  die Pfeile des Visits (kaum Änderung an deren Positionen), wird es verworfen
  und nach der nächsten Ruhephase neu versucht.

**Messung.** Nach dem nächsten Testlauf: Basisbilder mit Pfeilen (Farbzählung
wie oben), MISS-Phantome > 3000 mm², Phantome in den ersten 5 s nach dem Wechsel.
Ziel jeweils 0.

---

## 2. Gezogene Pfeile vor der Größenprüfung erkennen

**Befund.** `0a49c`, Visit 11 (der Checkout-Visit): **17-mal
`implausible_shape` in 30 s**, Fläche konstant 8870–9750 mm², Länge 253–266 mm,
`trigger_peak_blocks` teils 1–7. Das ist keine Person, sondern die Referenz mit
den drei gezogenen Pfeilen des Vorvisits — knapp über
`_MAX_BLOB_AREA_MM2 = 8000` und `_MAX_BLOB_LENGTH_MM = 250`. Die Größenprüfung
greift vor `changed_from_empty` (im Log `-1`), ein `implausible_shape` rollt die
Referenz nicht weiter, und der Zustand hält, bis der Visit endet. Alle drei
Pfeile, auch die D8, gingen von Hand.

Dieselbe Klasse knapp darunter: `darts_removed` mit 5525, 6635 und 7397 mm²
(`0a4ad`, `0a06c`). Mit großen Flights und naher Kamera reicht der Abstand zur
Grenze also nicht.

**Fix.**

1. `changed_from_empty` für den Blob auch dann berechnen, wenn er die
   Größengrenze reißt. Liegt er unter `_MIN_CHANGED_FROM_EMPTY`, ist das Ergebnis
   `DARTS_REMOVED` (absorbiert, Referenz rollt), nicht `IMPLAUSIBLE_SHAPE`.
2. Sicherheitsnetz im Socket: N aufeinanderfolgende `implausible_shape` mit
   praktisch gleicher Fläche (± 5 %) bei kleinem Trigger-Peak heißen „die
   Referenz ist veraltet“ → Rekalibrierung anfordern.

**Messung.** Offline: `0a49c` Visit 10 → Visit 11 lässt sich mit dem letzten Frame
von Visit 10 als Referenz und einem Frame des leeren Boards nachstellen. Testsatz
(285) muss unverändert bleiben.

---

## 3. Ring-Innenkanten nachmessen

**Befund.** Die Ringverwechslungen im selben Sektor sind einseitig:

| Richtung | Anzahl | Radien |
|---|---|---|
| Spitze innerhalb des erwarteten Rings | **22** | „S statt D“ ausnahmslos r 159–162, „S statt T“ r 97–99 |
| Spitze außerhalb | 5 | |

Unabhängig davon auf den Basisbildern gemessen: entlang von 60 Radien pro Bild
die Farbkanten von Triple und Double über die Homographie in Board-Millimeter
abgebildet (Median über alle Spiele):

| Kante | Modell | gemessen |
|---|---|---|
| Triple innen | 99.0 | **−3.1 mm** |
| Triple außen | 107.0 | −0.9 mm |
| Double innen | 162.0 | **−3.6 mm** |
| Double außen | 170.0 | −0.4 mm |

Getrennt nach schwarzem und beigem Nachbarbett verschieben sich die einzelnen
Kanten um ±1 mm (Farbunschärfe), die **Bandmitten liegen aber in beiden Fällen
~2 mm innen**. Im Overlay von `0a49c` throw7/dart1 (Truth D20, gewertet S20)
sitzt die Spitze sichtbar auf dem roten Band, innerhalb der Modell-Innenlinie.

Die Außenkante, auf die die Kalibrierung fittet, stimmt also; die Innenkanten
nicht. Zwei Kandidaten:

- `TRIPLE_INNER_RADIUS` / `DOUBLE_INNER_RADIUS` passen nicht zu diesem Board
  (Blade 6), die Ringe sind breiter als 8 mm.
- Die Homographie verzerrt radial, weil alle 20 Korrespondenzen auf einem
  einzigen Kreis (170 mm) liegen.

**Plan.**

1. Mit dem Lineal am Board: Innenbreite von Double und Triple, Radius der
   Außenkanten. Das entscheidet zwischen den beiden Kandidaten.
2. Stimmen die Maße nicht mit 99/162: Konstanten korrigieren. Stimmen sie: die
   Homographie mit zusätzlichen Korrespondenzen auf den Ringkanten (Triple,
   Double innen) verfeinern.
3. Die Kantenmessung als Skript nach `scripts/calibration/` — sie ist zugleich
   die in [kalibrierung.md §7](../feature/done/kalibrierung.md#7-offene-punkte) offene
   unabhängige Genauigkeitsmessung.

**Erwartung.** Kontrafaktisch auf den Live-Daten: Innenkanten 2.0 mm nach innen
→ +12 / −4, 2.5 mm → **+14 / −4**, 3.0 mm → +15 / −7. Das ist auf denselben
Daten bestimmt, auf denen der Befund entstand, und damit nur ein Hinweis auf die
Größenordnung — der Wert muss aus Schritt 1 kommen, nicht aus dieser Tabelle.

---

## 4. Orientierung bei steiler Kamera

**Befund.** In den steilen Setups (`0a0a1`, `0a49c`, `0a4a4`, 1.3–1.4 px/mm,
Kamera schräg von unten links) wird die Spitze am **Flight-Ende** gesetzt:

- MISS-Buchungen bei r ≈ 290–318 mm: **9 falsch** (Truth meist S20) und
  6 Phantome.
- Overlay `0a4a4` throw7/dart1: Achse korrekt, Spitze auf dem Flight. Der Blob
  besteht aus Flight und Schaft; das Barrel über dem schwarzen Bett fehlt, also
  entscheidet die Breitenmessung (§2.4 in [erkennung.md](../feature/done/erkennung.md)) auf einem
  Stück, das kaum ein breites und ein schmales Ende hat.
- `anchor_to_tip_mm < 30` trifft 10 falsche (> 5 mm) und 3 Phantome gegen nur
  4 korrekte — ein billiger Verdachtsindikator.

**Fix-Kandidaten** (in dieser Reihenfolge messen):

1. **Flight-Richtung als Kamera-Prior.** Pro Kamera zeigen die Flights nahezu in
   dieselbe Bildrichtung. Der gleitende Median der Achsrichtung (Spitze → Flight)
   der gebuchten Pfeile entscheidet, wenn die Breitenmessung knapp ist oder
   `anchor_to_tip` kurz.
2. **Board-Plausibilität.** Liegt ein Achsenende auf der Scoring-Fläche und das
   andere jenseits des Detektionsradius (225 mm), ist das innere die Spitze.

**Messung.** Kuratierter Testsatz unverändert; auf den Serien der drei Spiele die
MISS-Buchungen über 280 mm.

---

## 5. Mindestfläche für punktende Pfeile

**Befund.** Die Regel aus
[client-diff-verbesserungen.md §9](../feature/client-diff-verbesserungen.md#9-kleine-miss-blobs-verwerfen-server)
verwirft nur kleine `MISS`. Punktende Buchungen mit kleinem Blob:

| Fläche | falsch | Phantom | korrekt |
|---|---|---|---|
| < 150 mm² | 4 | 1 | 0 |
| < 250 mm² | 6 | 3 | 1 |
| < 400 mm² | 9 | 4 | 4 |

Korrekt gewertete Pfeile liegen pro Spiel bei mindestens 290–660 mm²
(Ausreißer 156 in Stand A).

Die MISS-Grenze selbst anzuheben ist dagegen **nicht** gratis: 17 der 30
MISS-Phantome haben 400–650 mm² (Zahlenring, r 208–230), aber im selben Band
liegen 22 korrekte MISS. Der Radius trennt ebenso wenig (korrekte
Surround-Pfeile r 172–241).

**Fix.** Punktende Blobs unter 250 mm² → `NO_CHANGE` (absorbiert wie ein
verworfener MISS). Die MISS-Grenze bleibt bei 400.

**Messung.** Auf dem kuratierten Testsatz prüfen, wie viele korrekte Pfeile
unter 250 mm² liegen — die schwarzen Pfeile und fernen Setups dort sind kleiner
als live.

---

## 6. Zu lange Blobs neu fusionieren statt verwerfen

**Befund.** Ein Teil der `implausible_shape` hat pfeilgroße Fläche (< 2000 mm²)
und scheitert nur an der Länge (253–575 mm), typischerweise 1–3 s nach einer
Buchung und bei kleinem Trigger-Peak. Beispiel `0a0a1` throw11: 438 mm² bei
313 mm, danach S20 von Hand. Ähnlich `0a0a1` throw15/20 und `0a051` throw8/12/13.

Dazu passt: auf 314 von 624 Buchungen folgt innerhalb von 2.5 s ein weiterer
Frame (270-mal `no_change`). Der Pfeil schwingt nach, und der Trigger feuert ein
zweites Mal.

**Fix.** Reißt ein Blob nur die Länge, die Fusion ohne die vom Anker
entferntesten Fragmente wiederholen, bis er unter die Grenze fällt; erst dann
aufgeben.

**Messung.** Anzahl `implausible_shape` mit Fläche < 2000 mm² und Folgebuchung
von Hand im selben Visit; Testsatz unverändert.

---

## 7. Rekalibrierung bei Kameraversatz

**Befund.** 17 Fits mit mehr als 10 px `alignment_shift_px` (bis 113 px) in
sechs Spielen. Ein Teil davon in der Aufbauphase, aber auch mitten im Spiel:
`0a051` throw16 (36 px → Phantom und `implausible_shape`), `0a4ad` throw19
(95 px), `0a49c` throw0 (72–113 px, drei Fehlschläge in Folge). Der Wert ist in
[kalibrierung.md §7](../feature/done/kalibrierung.md#7-offene-punkte) schon als Auslöser
vorgesehen, löst aber nichts aus.

**Fix.** `alignment_shift_px` über einer Schwelle (Vorschlag 10 px, Median im
Spiel liegt bei 0.1–1.3 px) → `calibration_requested` an diese Kamera, Frame
nicht buchen.

---

## 8. Testserien vollständig und treu schreiben

Drei Fehler im Aufzeichnen, die die Serien als Regressionssatz entwerten.

**8a — Der letzte Visit fehlt.** `recorder.settle_visit` läuft nur bei
`next_player`, ein gewonnenes Spiel endet ohne. In **allen** beendeten Spielen
fehlt der Checkout-Visit — also genau die Doppel-Würfe, die für die Wertung am
meisten zählen. Fix: auch schreiben, sobald `winner` gesetzt ist.

**8b — Frames geschluckter Pfeile.** `_handle_throw_frame` ruft
`recorder.note_throw` vor `register_dart`. Ein vierter Dart landet damit in der
Serie, ohne als Buchung zu zählen: `09750` throw9 (5 Frames, 4 Buchungen),
throw15 (2/1). `ground_truth.txt` wird frameweise vergeben und ist dort um eins
verschoben. Fix: Frame erst nach `_apply` und nur bei `changed` merken.

**8c — Absorbierte Frames fehlen.** Verworfene MISS und `darts_removed` rollen
live die Referenz weiter, stehen aber nicht in der Serie. Die Offline-Kette
differenziert deshalb gegen einen anderen Frame als live. Gemessen: dieselben
542 Frames mit dem heutigen Detektor nachgespielt ergeben in **72 Fällen ein
anderes Urteil** (49 schlechter, 23 besser), 79.3 % live gegen 74.5 % offline.
Das ist deutlich mehr als der „Rest, der keinen Punkt wert ist“, von dem §9 in
client-diff-verbesserungen.md ausging. Fix: absorbierte Frames mit in die Serie
schreiben; `report.py` labelt sie `NO_CHANGE`.

**Messung.** Nach dem Fix: nächster Testlauf offline nachspielen, Abweichung
live/offline muss auf Rauschen fallen.

---

## 9. Kalibrierungen ins Event-Log

**Befund.** Ob und wann eine Kamera kalibriert hat, steht nicht im Log. Das
Rennen aus Schritt 1 ließ sich nur über die Farbe in den Basisbildern
rekonstruieren, und ob eine Kalibrierung *fehlschlug*, gar nicht.

**Fix.** Eigenes Event `calibrated` (Erfolg oder `CalibrationFailure`, Anlass:
Wechsel, Anforderung, Versatz, `px/mm`). Damit sind Schritt 1, 2 und 7 direkt
messbar.

---

## 10. Report und Seite angleichen

- `report.py` zählt nicht beendete Spiele mit (`09a30`, `0974d`, `0a063`), die
  Seite unter `/account/evaluation` nicht — zwei verschiedene Kopfzahlen für
  „dieselbe“ Frage.
- „Games: 15“ zählt `0a062` mit, das kein einziges Judgement hat; die
  Pro-Spiel-Tabelle zeigt 14.
- Ein **korrekter MISS kann Zufall sein**: das Alignment vergleicht nur Labels,
  ein MISS-Phantom neben einem von Hand eingetragenen Abpraller zählt als
  `correct`. Die drei korrekten MISS bei r > 280 mm sind vermutlich solche Fälle.
  Kandidat: ein gebuchter MISS jenseits von 225 mm wird nicht mit einer
  Handeingabe gepaart, sondern als `phantom` + `missed` gezählt.

**Fix.** Report standardmäßig auf `finished_only`, mit Schalter für alle; Spiele
ohne Judgement nicht zählen; die MISS-Paarung im Report getrennt ausweisen,
bevor die Regel geändert wird.

---

## 11. Client-Trigger: Schritt 2 und 4 zurückstellen

**Befund.** Die Trigger-Metriken aus den Spielen ab Stand C trennen echte Würfe
nicht von Fehlauslösern:

| Regel | korrekt verloren | Phantome | `no_change` |
|---|---|---|---|
| Episoden-Peak > 48 (Schritt 2) | **38 / 374** | 11 / 27 | 84 / 897 |
| Timeout | 65 | 14 | 148 |
| Timeout und Peak > 30 | 40 | 13 | 92 |
| Höhe ≥ 7 Zeilen | 56 | 10 | 124 |

Der Wurfarm bzw. der Spieler ist bei diesen Aufbauten regelmäßig im Bild. Die
Frage aus [client-diff-verbesserungen.md §2](../feature/client-diff-verbesserungen.md#2-episoden-höchstwert-bricht-die-erfassung-ab-client)
ist damit beantwortet: eine Episoden-Grenze kostet rund 10 % Recall. Der Client
sendet im Median alle 1.3 s, 67 % der Fits sind `no_change` (8.7–20 pro Minute).

**Entscheidung.** Schritt 2 und 4 dort nicht umsetzen; der Hebel liegt auf dem
Server (Schritte 1, 2, 5, 6 hier). Die Fehlsendungsrate bleibt als Zahl für
Phase 4 stehen. Einzige Client-Änderung aus diesem Lauf ist das Halten der Frames
bis zur Rekalibrierung (Schritt 1).
