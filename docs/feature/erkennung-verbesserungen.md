# Erkennung: geplante Verbesserungen

Arbeitsplan für die nächste Runde an der Detektions-Pipeline. Die Pipeline
selbst ist in [erkennung.md](erkennung.md) beschrieben — dieses Dokument hält
fest, *was als nächstes warum* geändert wird, damit die Reihenfolge und die
Begründungen eine Session überdauern. Erledigte Schritte wandern inhaltlich nach
[erkennung.md](erkennung.md) und bleiben hier nur als Zeile in der Statustabelle
stehen.

**Ausgangslage:** neue Pfeile mit Wolfram-Spitzen (Spitzenerkennung deutlich
besser) und **einfarbig weißen Flights** (schlechter trennbar vom beigen Bett).
Testset auf 285 Paare über fünf Boards / 16 Setups gewachsen,
Stand **213/285 = 74.7 %** korrektes Segment.

Die Fehlerverteilung in `backend/testdata/detection/_results/accuracy.md` zerfällt
in zwei Klassen: 33 der 72 Mismatches liegen **unter 5 mm** vom erwarteten Segment
(Draht-Breite, Präzisionsgrenze — die bleiben), der Rest sind Fehler mit einer
strukturellen Ursache. Dieser Plan zielt ausschließlich auf die zweite Klasse.

---

## Status

| # | Schritt | Aufwand | Status |
|---|---|---|---|
| 1 | [Warp-Gültigkeitsmaske](#1-warp-gültigkeitsmaske) | S | **erledigt** — 75.8 % → 76.5 % |
| 2 | [Gradientenabhängiger Schwellwert + Anker-Constraint](#2-gradientenabhängiger-schwellwert--anker-constraint) | S | offen |
| 3 | [Sättigungskanal + weiß-basierte Flight-Wahl](#3-sättigungskanal--weiß-basierte-flight-wahl) | M | offen |
| 4 | [Extrapolation in schwarze Segmente](#4-extrapolation-in-schwarze-segmente) | M | offen |
| 5 | [Homographie-Residuum messen](#5-homographie-residuum-messen) | M | offen |
| 6 | [Ambiguitäts-Guard](#6-ambiguitäts-guard) | S | offen |

Nach jedem Schritt `scripts/detection/run_all.py` laufen lassen und die
Accuracy-Tabelle in [erkennung.md §6](erkennung.md#6-stand-der-messungen)
fortschreiben — dieselbe A/B-Disziplin wie bei den ersten vier Entwicklungs-
schritten. Ohne Vorher/Nachher-Zahl gilt ein Schritt nicht als erledigt.

---

## 1. Warp-Gültigkeitsmaske

**Befund.** `detect_dart` warpt den ankommenden Frame mit `cv2.warpPerspective`
auf die Referenz. Wo der Kameraversatz Pixel aus dem Quellbild herausschiebt,
füllt OpenCV mit **Schwarz**. Die Differenz gegen die Referenz beträgt dort
200+ Graustufen — das Fünffache des Schwellwerts, und zwar als langer, *breiter*
Streifen am Bildrand.

Damit gewinnt der Streifen die Flight-Wahl in `_fuse_dart_fragments`, die das
**breiteste** Fragment als Flight nimmt. Der Anker sitzt dann außerhalb des
Boards und die gefittete Gerade zeigt irgendwohin.

Belegt an `pz-light_setup3/throw7`:

- `dart1`: `03_difference.jpg` meldet `peak difference 251` — das ist der
  Randstreifen bei x≈0, nicht der Pfeil. **73 Komponenten**, Flight-Anker
  außerhalb des Boards, Spitze bei r=225.0 mm → `MISS` statt `S7`, **227 mm**
  daneben.
- `dart2`: der Flight wird korrekt gefunden, aber ein Randfragment wird
  mitgefused und zieht die Achse nach links oben → `S14` statt `S8`, **49 mm**.

**Fix.** Denselben Warp auf ein weißes Bild anwenden, das Ergebnis ist die Maske
der gültigen Pixel; um ein paar Pixel erodieren, weil die bilineare Interpolation
die Kante verschmiert; in die `search`-Maske hineinschneiden, *bevor*
geschwellt wird.

```python
valid = cv2.warpPerspective(np.full(frame.shape[:2], 255, np.uint8), alignment, size)
valid = cv2.erode(valid, kernel)
search = cv2.bitwise_and(search, valid)
```

**Dazu.** Bei `pz-light_setup3` ragt das Board links aus dem Bild (die Zahlen
„14" und „9" sind angeschnitten). Das ist ein Framing-Problem, kein Algorithmus-
Problem, und die beiden müssen unterscheidbar sein: im Trace vermerken, wenn die
`region`-Kontur außerhalb des Bildes liegt, und in den Debug-Bildern zeichnen.

**Erwartung.** Die drei Fälle über 150 mm und mehrere der 40–120 mm-Fälle.

### Ergebnis (erledigt)

Implementiert als `_warp_coverage` in `dart_detector.py`, plus
`trace.observed` / `trace.unobserved_region` / `trace.region_clipped` und deren
Darstellung in `01_region.jpg` (magenta = nicht abgedeckte Board-Fläche, plus
eine Warnzeile, wenn das Board aus dem Bild ragt).

**Gemessen: 216/285 → 218/285, 75.8 % → 76.5 %** (beide Zahlen unter derselben
Metrik, siehe unten; zwei aufeinanderfolgende volle Läufe, identisches Ergebnis).
Deutlich weniger als erwartet, und das Warum ist die eigentliche Erkenntnis.

Drei Fälle haben sich geändert:

- `pz-light_setup3/throw7/dart2`: `S14` → **`S8`**, korrekt (vorher 49 mm daneben).
- `pz-light_setup1/throw5/dart2`: → **`S3`**, korrekt.
- `pz-light_setup1/throw8/dart2`: vorher als Treffer gezählt, jetzt `NO_CHANGE`.
  Die Truth ist `MISS`, und der Pfeil ist tatsächlich nirgends auf dem Board —
  vorher hat die Pipeline den Randstreifen gefunden, ihn außerhalb von 170 mm
  verortet und **aus dem falschen Grund** `MISS` gemeldet. Unter der korrigierten
  Metrik (`NO_CHANGE` = `MISS`, siehe
  [erkennung.md §3](erkennung.md#no_change-ist-punktemäßig-ein-miss)) zählt dieser
  Fall weiterhin als Treffer — jetzt aus dem richtigen Grund.

**Metrik-Hinweis.** Zwischen den beiden Messungen wurde die Auswertung geändert:
`NO_CHANGE` gegen ein erwartetes `MISS` zählt jetzt als korrekt, weil beides null
Punkte bedeutet. Die alte Rohzahl war 213/285 (74.7 %), die neue 218/285 (76.5 %)
— aber vier davon sind der Metrik geschuldet, nicht dem Algorithmus. Um die
Zahlen vergleichbar zu halten, ist die Baseline oben nachträglich unter derselben
Regel ausgewertet (213 + 3 `NO_CHANGE`-gegen-`MISS` = 216). **Netto sind es zwei
Pfeile.**

Die Abstandsverteilung der verbleibenden Mismatches zeigt, dass das Grundproblem
bleibt:

| | ≤5 mm | 5–20 | 20–50 | >50 | Mittel | Max |
|---|---|---|---|---|---|---|
| vorher | 33 | 12 | 6 | 18 | 35.2 | 227.4 |
| nachher | 32 | 12 | 5 | 18 | 35.3 | 220.0 |

**Warum so wenig.** Der Randstreifen war nur *eine* Quelle breiter, heller
Fremdfragmente. `pz-light_setup3/throw7/dart1` etwa ankert jetzt statt auf dem
Warp-Rand auf den **weißen Board-Zahlen** („12", „9", „14") im Surround, die der
Registrierungs-Restfehler aufleuchten lässt — 227 mm wurden zu 220 mm. Dieselbe
Fehlerklasse, andere Quelle.

Der Schritt bleibt trotzdem richtig: er entfernt ein Artefakt, das gar keine
Änderung im Bild ist, und ohne ihn wäre die Anker-Constraint aus Schritt 2 nicht
formulierbar (der Anker muss in der beobachteten Fläche liegen). Die Lehre für
die Reihenfolge: **Schritt 2 ist der eigentliche Hebel**, Schritt 1 war seine
Voraussetzung.

**Nebenergebnis.** `region_clipped` meldet für `pz-light_setup3`, dass **30 %**
der Board-Kontur außerhalb des Bildes liegen. Das Setup ist schlicht zu knapp
gerahmt — ein Aufnahme-Befund, der bisher als Detektionsfehler durchging.

---

## 2. Gradientenabhängiger Schwellwert + Anker-Constraint

**Befund.** In `05_cleanup.jpg` überleben die weißen Board-Zahlen („14", „9",
„12", „16"), der weiße Außenring und Drahtkanten den Schwellwert. Ursache ist ein
Sub-Pixel-Rest der Registrierung: ein lokaler Versatz δ erzeugt eine Differenz von
etwa |∇I|·δ. Auf den glatten Betten, wo der Pfeil liegt, ist ∇I≈0; an Zahlen und
Drähten ist er groß. Ein *konstanter* Schwellwert ist damit an der falschen Stelle
streng.

Gemessen an `pz-light_setup2/throw5/dart1` (Hintergrund = Suchbereich ohne den
Pfeil, 341 246 px):

| Gradienten-Dezil (Sobel) | mittlere Differenz |
|---|---|
| 0 – 2 | 0.6 |
| 12.6 – 21.6 | 3.3 |
| 21.6 – 63 | 4.8 |
| 63 – 906 | **12.4** |

Die 561 Hintergrundpixel über dem Schwellwert von 40 haben einen mittleren
Gradienten von **415** — sie liegen also fast ausschließlich auf Kanten. Nach
Helligkeit sortiert ergibt sich kein vergleichbarer Trend, und der globale
Helligkeitsunterschied zwischen den beiden Frames beträgt nur 1.4 % (kein
Belichtungssprung). Der Zusammenhang ist eindeutig der Gradient.

**Wichtig: das ist nicht Kamerawackeln.** Bei genau diesem Fall beträgt der
gemessene Kameraversatz über die Board-Kontur **0.2 px** — die Registrierung
sitzt praktisch perfekt, und das Board-Modell liegt im Overlay exakt auf den
echten Drähten. Der Rest-Versatz ist *lokal* und überlebt auch einen perfekten
globalen Fit: JPEG-Artefakte, nicht modellierte Objektivverzeichnung und der
Tiefenunterschied zwischen Board und Surround. Ein besserer Fit oder eine
Neuberechnung der Homographie holt das deshalb nicht zurück — nur ein
Schwellwert, der weiß, wo im Bild er streng sein muss.

**Fix a.** Schwellwert gradientenabhängig machen: `difference > 40 + k·|∇reference|`,
mit einem Sobel plus Blur einmal pro Frame auf der Referenz. Pfeil-Pixel behalten
die 40, Kantenpixel brauchen deutlich mehr.

**Fix b.** `_drop_unanchored` wirft an diesen Frames **0 px** weg: die
Draht-Residuen liegen überall in `region`, und über den 90-mm-Reach verkettet
sich alles bis nach außen. Zusätzliche Bedingung an der Ankerwahl: der
Flight-Anker muss innerhalb `search` **und** innerhalb der Gültigkeitsmaske aus
Schritt 1 liegen. Ein Anker außerhalb des Boards ist per Definition kein Flight.

**Nach Schritt 1 der eigentliche Hebel.** Dort hat sich gezeigt, dass der
Warp-Rand nur eine von mehreren Quellen breiter, heller Fremdfragmente war;
`pz-light_setup3/throw7/dart1` ankert seither auf den weißen Board-Zahlen im
Surround. Die 18 Mismatches über 50 mm sind fast durchweg dieses Muster.

**Erwartung.** Die 20–70 mm-Fälle und ein großer Teil der >50 mm-Fälle.

---

## 3. Sättigungskanal + weiß-basierte Flight-Wahl

**Befund.** Gemessen an `pz-light_setup3` (Sättigung auf der 0–255-Skala von
OpenCVs HSV):

| | S | V |
|---|---|---|
| beiges Bett | 51–58 | 225 |
| weißer Flight | 26–30 | 220 |
| schwarzes Bett | 11 | 45 |

In **BGR** ist der weiße Flight über einem beigen Bett praktisch unsichtbar: die
größte Kanaldifferenz beträgt etwa 14, der Schwellwert ist 40. In der
**Sättigung** sind es rund 29. Der Kanal, der die neuen Flights trägt, wird
aktuell also gar nicht ausgewertet — `absdiff` läuft nur über BGR.

**Fix a.** Den S-Kanal in die Differenz aufnehmen, mit eigenem, niedrigerem
Schwellwert.

**Fix b.** Den Flight *positiv identifizieren* statt „breitestes Fragment":
das Fragment mit den meisten Weiß-Pixeln. Das ist immun gegen einen breiten
Rauschblob — die Hauptschwachstelle der aktuellen Ankerwahl (siehe Schritt 1).
Fallback auf die Breite, wenn kein Fragment qualifiziert (dunkle Flights).

**Einschränkung — das ist der eigentliche Knackpunkt.** Ein absoluter
S-Schwellwert funktioniert nicht. Über die 16 Setups streut die Sättigung des
beigen Betts von 42 (`cc_setup1`) bis 104 (`fh_setup2`), abhängig von Board-Alter
und Weißabgleich:

| Setup | beige S (Mittel) | Setup | beige S (Mittel) |
|---|---|---|---|
| cc_setup1 | 41.8 | pz_setup2 | 67.7 |
| pz-light_setup1 | 50.0 | pz_setup4 | 71.1 |
| pz-light_setup2 | 50.4 | tz_setup2 | 72.0 |
| cc_setup2 | 54.5 | pz_setup1 | 73.5 |
| tz_setup5 | 58.1 | pz_setup3 | 76.6 |
| pz-light_setup3 | 58.2 | tz_setup3 | 88.1 |
| tz_setup4 | 61.7 | tz_setup1 | 94.3 |
| | | fh_setup1/2 | 103.1 / 103.9 |

Die Schwelle muss deshalb **pro Frame** referenziert werden. Das geht sauber,
weil die Homographie exakt sagt, *wo* die beigen Betten liegen: deren Sättigung
sampeln, Median bilden, Schwelle bei etwa 0.6× davon. Das Board liefert seinen
eigenen Farbreferenzpunkt — für die Arbeit die interessantere Formulierung als
ein empirisch getunter Schwellwert.

---

## 4. Extrapolation in schwarze Segmente

**Befund.** Ein dunkler Pfeil difft nur über hellen Betten. Läuft die Spitze in
ein schwarzes Segment, endet die Maske an der **Farbkante**, nicht an der Spitze
— und genau dort wird gescort. Der menschliche Bewerter macht es anders: ist das
angrenzende beige Feld bis zur Grenze hin voll vom Pfeil überdeckt, steckt die
Spitze im schwarzen Nachbarfeld, auch ohne sie zu sehen.

**Fix.** Das lässt sich ohne zusätzliche Bildinformation formalisieren, weil die
Board-Farben analytisch bekannt sind (`board_geometry.py`). Die Maske endet an
einem Punkt P; über die Homographie ist bekannt, welche Farbe das Board bei P hat.

- Board bei P **hell** → die Silhouette endet echt dort, P ist die Spitze.
- Board wird bei P innerhalb 1–2 mm **schwarz** → die Maske endet an der
  Farbkante. Entlang der gefitteten Achse extrapolieren, bis das Board wieder
  hell wird oder ein Deckel greift.

Gedeckelt (höchstens eine Segmentbreite) und nur bei gut bestimmter Achse. Damit
wird die Abbruchstelle von einem Fehler zu einer Information.

**Priorität.** Durch die Wolfram-Spitzen nicht mehr der Hauptfehler, adressiert
aber den in [erkennung.md §6](erkennung.md#6-stand-der-messungen) dokumentierten
Restfehler des farb-gegateten Signals.

---

## 5. Homographie-Residuum messen

**Frage.** Stimmt die Homographie überhaupt genau genug für Millimeter-Angaben,
oder verschiebt sich die Kamera minimal? Naheliegende Reaktion wäre, die
Homographie nach jedem Wurf neu zu berechnen.

**Warum nicht neu rechnen.**

- Der Kameraversatz **wird** bereits kompensiert — dafür ist die
  ORB-Registrierung da, und sie liefert an diesen Frames 2412–2907 RANSAC-Inlier.
  Ein Verrutschen ist nicht die Fehlerquelle.
- Ein Ellipsen-Fit pro Frame ist **messbar schlechter**:
  [erkennung.md §5.3](erkennung.md#53-zwei-unabhängige-ellipsen-fits-statt-registrierung)
  dokumentiert 7 % Achsendrift zwischen zwei unabhängigen Fits aufeinander-
  folgender Frames einer Serie. Das zerstört zusätzlich die Differenzbasis, auf
  der die ganze Pipeline steht.

**Stattdessen messen.** Die Modell-Geometrie (20 Sektorgrenzen, 4 Ringradien)
durch die inverse Homographie ins Basisbild projizieren und den Abstand zu den
tatsächlich detektierten Drahtpixeln in Millimetern reporten, pro Setup. Damit
wird aus einem Bauchgefühl eine Zahl.

**Teilweise erledigt.** `run_all.py` zeichnet dieses Modell inzwischen in cyan in
jedes annotierte Bild (`draw_board_model`, über `board_overlay.build_overlay`).
Damit ist bei jedem Mismatch mit einem Blick zu sehen, ob die Ringe auf den echten
Ringen sitzen — ein Kalibrierungsfehler und ein Detektionsfehler sahen bis dahin
gleich aus. Ebenso trägt jedes Bild und jede Report-Zeile jetzt den gemessenen
**Kameraversatz** (`trace.alignment_shift_px`, mittlere Verschiebung der
Board-Kontur unter der Alignment-Homographie), und der Report gruppiert die
Genauigkeit danach.

Was noch fehlt, ist die *numerische* Residuen-Messung gegen die echten
Drahtpixel — das Overlay ist bisher eine Sichtprüfung.

**Beantwortet: Kamerawackeln ist in diesem Testset nicht das Problem.**

| Kamerabewegung | korrekt | gesamt | Quote | mittl. Abweichung |
|---|---|---|---|---|
| < 2 px (still) | 208 | 276 | 75 % | 8.6 mm |
| 2 – 5 px | 5 | 8 | 62 % | 1.3 mm |
| 5 – 10 px | 1 | 1 | 100 % | 0.0 mm |

**276 von 285 Paaren (97 %) bewegen sich unter 2 px**, und von den 71 Mismatches
haben nur drei mehr als 2 px — zwei davon sind Beinahe-Treffer (3.1 mm, 5.7 mm).
Die Paare mit der größten Bewegung liegen im Schnitt *näher* am richtigen Segment
als die stillen. Ein Zusammenhang zwischen Bewegung und Fehler ist nicht messbar.

*Einschränkung:* die Testaufnahmen entstanden mit ruhig aufgestellter Kamera. Für
den freihändigen Live-Betrieb sagt das nichts — dafür ist der Drift-Watchdog
weiterhin sinnvoll, jetzt mit `alignment_shift_px` als fertiger Messgröße.

Verdachtsfall: `tz_setup5` hat auffällig viele fälschlich als `MISS` gescorte
Pfeile — wenn dort ein systematischer Auswärtsversatz messbar ist, gehört die
Korrektur in die Kalibrierung, nicht in die Detektion.

**Separat davon** (steht schon in [todo.md](../todo.md)): ein Drift-Watchdog —
überschreitet die Alignment-Homographie eine Translationsschwelle, Re-Kalibrierung
anfordern statt weiterrechnen.

---

## 6. Ambiguitäts-Guard

**Befund.** Die Pipeline nimmt implizit an, dass genau ein neues Objekt in der
Maske liegt. Nach dem Rand-Fix bleiben die Fälle „vorheriger Pfeil wurde
angestoßen" und „Pfeil ist wieder abgefallen" — dann ist die Maske mehrdeutig,
und die Fusion entscheidet sich still für eine Variante.

**Fix.** Bleibt nach der Fusion ein zweiter, vergleichbar großer, nicht
kollinearer Cluster übrig, ist das Ergebnis unsicher → melden statt still
scoren. Hängt direkt am Todo „client diff löst öfter aus, das Backend muss das
prüfen".

**Erwartung.** Kein Accuracy-Gewinn, sondern Robustheit im echten Spiel.
