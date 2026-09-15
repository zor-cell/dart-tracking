# Erkennung: geplante Verbesserungen

Arbeitsplan für die nächste Runde an der Detektions-Pipeline. Die Pipeline
selbst ist in [erkennung.md](done/erkennung.md) beschrieben — dieses Dokument hält
fest, *was als nächstes warum* geändert wird, damit die Reihenfolge und die
Begründungen eine Session überdauern. Erledigte Schritte wandern inhaltlich nach
[erkennung.md](done/erkennung.md) und bleiben hier nur als Zeile in der Statustabelle
stehen.

Es geht hier ausschließlich um die **Genauigkeit** der Pipeline: gegeben ein
Frame mit einem Pfeil, wie genau wird die Spitze getroffen. Ob überhaupt ein
sinnvoller Frame ankommt, plant
[client-diff-verbesserungen.md](client-diff-verbesserungen.md) — dort liegt auch
die fehlende Größen-Ablehnung, die zwar im Detektor sitzt, aber ein
Trigger-Problem löst.

**Ausgangslage:** das Testset enthält jetzt zwei gegenläufige Pfeil-Typen —
die alten dunklen (`pz`, `tz`) und die neuen mit Wolfram-Spitzen und **einfarbig
weißen Flights** (`cc`, `fh`, `pz-light`). 285 Paare über fünf Boards / 16 Setups.
Ausgangsstand **216/285 = 75.8 %**, aktueller Stand **226/285 = 79.3 %**
(Metrik: `NO_CHANGE` gegen ein erwartetes `MISS` zählt als korrekt, siehe
[erkennung.md §3](done/erkennung.md#no_change-ist-punktemäßig-ein-miss)).

Die Fehlerverteilung in `backend/testdata/detection/_results/accuracy.md` zerfällt
in zwei Klassen: 32 der 67 Mismatches liegen **unter 5 mm** vom erwarteten Segment
(Draht-Breite, Präzisionsgrenze — die bleiben), der Rest sind Fehler mit einer
strukturellen Ursache. Dieser Plan zielt ausschließlich auf die zweite Klasse.

---

## Status

| # | Schritt | Aufwand | Status |
|---|---|---|---|
| 1 | [Warp-Gültigkeitsmaske](#1-warp-gültigkeitsmaske) | S | **erledigt** — 75.8 % → 76.5 % |
| 2 | [Gradientenabhängiger Schwellwert](#2-gradientenabhängiger-schwellwert-verworfen) | S | **verworfen** — brachte 77.5 %, kostete aber auf dem dunkelsten Board zwei Pfeile; Code wieder entfernt, Messungen bleiben hier |
| 3 | [Ortsabhängiger Schwellwert, HSV für helle Betten](#3-ortsabhängiger-schwellwert-hsv-für-helle-betten) | M | **geteilt** — Schwellwert **verworfen** (monoton schlechter, 4 Varianten); S-Kanal **erledigt**, 76.5 % → 77.9 %. Beides in [erkennung-blob.md](erkennung-blob.md) |
| 4 | [Extrapolation in schwarze Segmente](#4-extrapolation-in-schwarze-segmente) | M | offen |
| 5 | [Homographie-Residuum messen](#5-homographie-residuum-messen) | M | teilweise (Overlay + Kameraversatz erledigt) |
| 6 | [Ambiguitäts-Guard](#6-ambiguitäts-guard) | S | offen |
| 7 | [Der Pfeil muss als ein Blob ankommen](erkennung-blob.md) | L | **in Arbeit — das eigentliche Ziel**, dem die Schritte oben zuarbeiten. Blob-Metriken (§6.5) und Fusions-Reichweite (§6.1b) erledigt, 77.9 % → **79.6 %**; Anker-Umsortierung (§6.1) verworfen |

Nach jedem Schritt `scripts/detection/run_all.py` laufen lassen und die
Accuracy-Tabelle in [erkennung.md §6](done/erkennung.md#6-stand-der-messungen)
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
  [erkennung.md §3](done/erkennung.md#no_change-ist-punktemäßig-ein-miss)) zählt dieser
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
Änderung im Bild ist — es entsteht erst durch den Warp. Die Lehre für die
Reihenfolge fiel anders aus als gedacht: Schritt 2 sollte der eigentliche Hebel
sein und wurde am Ende verworfen (siehe dort). Die Fragmentierung des Pfeils
selbst anzugehen — Schritt 3 — ist der verbliebene große Posten.

**Nebenergebnis.** `region_clipped` meldet für `pz-light_setup3`, dass **30 %**
der Board-Kontur außerhalb des Bildes liegen. Das Setup ist schlicht zu knapp
gerahmt — ein Aufnahme-Befund, der bisher als Detektionsfehler durchging.

---

## 2. Gradientenabhängiger Schwellwert  *(verworfen)*

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

### Der erste Versuch war falsch herum

Der naheliegende Weg — den gradientenabhängigen Schwellwert direkt auf die Maske
anwenden — ist **messbar schlechter**. Über die vollen 285 Paare:
**218 → 173 (76.5 % → 60.7 %)**, bei gleichzeitig *besseren* Abständen (mittlere
Abweichung 35.3 → 25.3 mm, Maximum 220 → 135 mm) und mehr Fällen unter 5 mm
(32 → 51).

Das Muster erklärt sich selbst: die strukturellen Ausreißer verschwinden, aber
der Pfeil verliert Pixel. Seine **Spitze** ist klein, kontrastarm und liegt oft
direkt neben einem Draht — genau dort, wo der Schwellwert angehoben wird. Eine
verkürzte Achse setzt die Spitze auf die falsche Seite eines Rings, und aus
einem großen Fehler wird ein kleiner statt gar keiner. Der Sweep über die
Toleranz zeigt den Zielkonflikt sauber (`pz-light`, 90 Paare):

| Toleranz | Quote | ≤5 mm | >20 mm | mittl. Abw. | max |
|---|---|---|---|---|---|
| 0.0 (aus) | 82.2 % | 7 | 9 | 48.6 | 220 |
| 0.2 | 83.3 % | 7 | 7 | 34.0 | 167 |
| 0.4 | 75.6 % | 15 | 6 | 15.6 | 116 |
| 0.8 | 67.8 % | 19 | 7 | 18.1 | 135 |

### Die Auflösung: zwei Schwellwerte mit zwei Aufgaben

Der Fehler war, einen Schwellwert zwei Fragen beantworten zu lassen. Getrennt:

- **Der flache Schwellwert (40) sagt, wie weit eine Änderung reicht.** Er baut
  die Maske und bestimmt damit die Ausdehnung des Pfeils — inklusive der
  kontrastarmen Spitze.
- **Der gradientenabhängige Schwellwert sagt, ob es überhaupt eine Änderung
  ist.** Er erzeugt eine *Seed*-Maske. Eine Komponente wird nur geglaubt, wenn
  mindestens `_MIN_SEED_FRACTION` ihrer Pixel darin liegen.

Ein Draht oder eine Board-Zahl ist auf ganzer Länge Kante — fast nichts davon
übersteht den strengen Schwellwert, die Komponente fliegt **ganz** raus. Ein
Pfeil liegt überwiegend auf flachem Bett, wo der strenge Schwellwert auf seinem
Minimum sitzt, also übersteht der Großteil. Behalten wird er dann aber in voller
Ausdehnung, sodass nichts am zu scorenden Ende abgeschnitten wird.

Dieselbe Idee wie Cannys Hysterese: streng entscheiden *wo* etwas ist, großzügig
bestimmen *wie weit* es reicht.

**Parameterwahl.** Gesweept über beide Pfeil-Populationen getrennt, weil sie
gegenläufig sind:

| Toleranz / Seed-Anteil | `pz-light` (weiß) | `tz` (schwarz) |
|---|---|---|
| aus | 82.2 % | 72.0 % |
| 0.4 / 25 % | 83.3 % | 72.0 % |
| 0.4 / 50 % | 83.3 % | 73.3 % |
| **0.8 / 25 %** | **83.3 %** | **74.7 %** |
| 0.8 / 50 % | 83.3 % | 70.7 % |

`0.8 px` Toleranz bei `25 %` Seed-Anteil gewinnt auf beiden. Die Toleranz ist
dabei keine gemessene Kamerabewegung (die liegt bei 0.2 px), sondern der
angenommene *lokale* Rest-Versatz.

### Verworfen: Ausnahme für die Scoring-Fläche

*Idee:* Komponenten, die in die Scoring-Fläche (170 mm) hineinreichen, vom
Seed-Test ausnehmen. Begründung: dort ist das Board flach und unbedruckt, und
alles, was der Test fangen soll — Zahlen, Außenring, Rand gegen die Wand —
liegt außerhalb.

*Warum verworfen:* **kostet drei Pfeile.** Die Sektordrähte laufen bis in die
Mitte, ihre Residuen erreichen die Scoring-Fläche also genauso leicht wie ein
Pfeil. Gemessen: `fh` +1, aber `cc` −1, `pz-light` −1, `tz` −2.

### Messergebnis

**218/285 → 221/285, 76.5 % → 77.5 %.** Drei Pfeile — und **wieder entfernt**,
siehe „Entscheidung" am Ende dieses Abschnitts.

Die Verteilung bewegt sich deutlicher als die Quote — und das ist die
interessantere Zahl, weil sie die Fehler*art* betrifft:

| | ≤5 mm | 5–20 | 20–50 | >50 | Mittel | Max |
|---|---|---|---|---|---|---|
| vor Schritt 2 | 32 | 12 | 5 | 18 | 35.3 | 220.0 |
| nach Schritt 2 | 29 | 12 | 9 | 13 | 28.1 | 166.6 |

Die **>50 mm-Fälle gehen von 18 auf 13** zurück, das Maximum von 220 auf 167 mm.
Der strukturelle Schwanz schrumpft also, ohne dass die Präzision leidet.

Pro Board: `tz` 54→56, `pz` 44→46, `pz-light` 74→75, `cc` 23→23, **`fh` 23→21**.

**Der `fh`-Rückgang ist ein echter Preis, kein Rauschen.** `fh` und `cc` hatten
vor Schritt 2 **null** Mismatches über 20 mm (mittlere Abweichung 4.2 bzw.
3.4 mm) — dort gibt es kein strukturelles Problem, das Gate kann nur schaden.
`fh` ist zugleich das dunkelste Setup (Bett-Helligkeit 171–176 gegen 225 bei
`pz-light`), das Pfeil-Signal also insgesamt schwächer, sodass eher eine
Komponente unter den Seed-Anteil rutscht. Der Gewinn kommt genau von den Boards
*mit* Ausreißern. Das ist als Bedingung formulierbar: **das Gate hilft, wo das
Front-End-Signal stark genug ist, dass Kanten-Residuen die einzige
Verwechslungsgefahr sind.** Bei schwachem Signal überwiegt der Verlust.

Beispiele, die es löst:

- `pz-light_setup3/throw7/dart1`: 74 Komponenten → **4**, Anker jetzt der echte
  Flight, Ergebnis `S7` statt `MISS` (war 220 mm daneben).
- `pz-light_setup2/throw5/dart1`: 112 Komponenten → **3**, r=223.5 mm → 171.8 mm.
  Immer noch ein Mismatch, aber nur noch knapp — jetzt ein Präzisionsfall
  (Signal endet an der Farbkante) und damit ein Fall für Schritt 4.

### Entscheidung: verworfen

Drei Pfeile über 285 Paare rechtfertigen das Risiko nicht. Der Gewinn kommt
ausschließlich von den Boards *mit* strukturellen Fehlern; auf dem dunkelsten
Board kostet das Verfahren zwei. Ein Front-End-Schritt, der bei schwacher
Ausleuchtung Genauigkeit *kostet*, ist für unbekannte Setups die falsche Wette —
und unbekannte Setups sind der Zweck des ganzen Systems.

Der Code ist entfernt (`_threshold_map`, `_drop_unseeded`, die vier Konstanten
und die zugehörigen Trace-Felder). Der aktuelle Stand ist wieder **218/285 =
76.5 %**, verifiziert. Die Messungen bleiben hier und in
[erkennung.md §5.11](done/erkennung.md#511-gradientenabhängiger-schwellwert-gegen-registrierungs-reste)
stehen, weil das Negativergebnis für die Arbeit brauchbar ist: es benennt die
**Bedingung**, unter der Kanten-Gating trägt.

Nicht verworfen ist die *Diagnose*. Dass die Fusion auf breiten hellen
Fremdfragmenten ankert, bleibt eine reale Fehlerursache — sie muss nur anders
angegangen werden als über den Schwellwert. Schritt 3 setzt eine Ebene früher an:
wenn der Pfeil als *ein* Blob ankommt statt als Streu-Fragmente, ist die
Anker-Wahl gar nicht mehr die kritische Entscheidung.

---

## 3. Ortsabhängiger Schwellwert, HSV für helle Betten

**Der wichtigste Schritt.** Die eigentliche Fehlerursache ist, dass der Pfeil
über einem gleichfarbigen Bett *verschwindet* und die Maske ihn dadurch in
Fragmente zerlegt — oder ihn stückweise ganz verliert. Das ist kein
Randphänomen; es ist der Grund, warum die Fusion überhaupt gebraucht wird.

### Es geht in beide Richtungen

Wichtig, weil die bisherige Doku es einseitig darstellt: das Problem ist
**symmetrisch**, und beide Fälle liegen im selben Testset.

| | Pfeilteil | Bett | Folge |
|---|---|---|---|
| dunkle Pfeile (`pz`, `tz`) | Barrel, Schaft, Spitze | schwarz | Spitze verschwindet, Achse endet an der Farbkante |
| Wolfram-Pfeile (`cc`, `fh`, `pz-light`) | weißer Flight | beige | Flight verschwindet, Orientierung kippt |

Derselbe Mechanismus, gespiegelt. „Helleres Pfeilmaterial" ist deshalb keine
Lösung, sondern verschiebt nur, *welche* Betten blind sind — das ist bereits als
Ergebnis in [erkennung.md §7](done/erkennung.md#7-offene-punkte) festgehalten. Was
fehlt, ist ein Front-End, das beide Fälle trägt.

**Gemessen** (`pz-light_setup3`, HSV auf OpenCVs 0–255-Skala für S und V):

| | H | S | V |
|---|---|---|---|
| beiges Bett | ~19 | 51–58 | 225 |
| weißer Flight | ~19 | 26–30 | 220 |
| schwarzes Bett | — | 11 | 45 |

Der weiße Flight über beigem Bett hat in **BGR** eine maximale Kanaldifferenz
von etwa **14** — der Schwellwert ist 40, er ist also unsichtbar. In der
**Sättigung** sind es rund **29**. Der Kanal, der die Unterscheidung trägt, wird
aktuell gar nicht ausgewertet: `absdiff` läuft nur über BGR.

### Messung: was der dunkle Pfeil auf schwarzem Bett wirklich hergibt

Diese Messung war offen und ist jetzt gemacht — mit einem Ergebnis, das die
Stoßrichtung dieses Schritts korrigiert.

**Methode.** Entlang der gefitteten Achse **korrekt gescorter** Würfe wird die
Barrel-/Schaft-Hälfte in 30 Schritten abgetastet und der ausgerichtete Frame
gegen die Referenz am *selben Pixel* verglichen — genau die Differenz, die die
Pipeline sieht. Die Bettfarbe kommt aus der Geometrie (rote Sektoren tragen die
schwarzen Single-Betten), nicht aus dem Bild. Dazu eine **Kontrollmessung** auf
leerem Bett, weit weg von jeder Änderung: ohne die ist nicht zu unterscheiden,
ob ein Kanal Signal liefert oder nur rauscht.

Dunkle Pfeile (`pz`, `tz`), Werte auf OpenCVs 0–255-Skala:

| Bett | Kanal | Pfeil | leeres Bett | Verhältnis |
|---|---|---|---|---|
| **schwarz** | max\|ΔBGR\| | 40.5 (Median 31.2) | 4.1 | **9.9×** |
| schwarz | ΔV | 38.3 | 3.0 | **12.8×** |
| schwarz | ΔS | 63.3 | 26.9 | 2.4× |
| schwarz | ΔH | 21.5 | 14.8 | 1.5× |
| hell | max\|ΔBGR\| | 100.9 | 4.5 | 22.4× |
| hell | ΔV | 99.5 | 3.3 | 30.2× |
| hell | ΔS | 53.0 | 4.0 | 13.3× |
| hell | ΔH | 10.4 | 1.7 | 6.1× |

**Die Sättigung ist auf schwarzem Bett eine Falle.** Roh betrachtet sieht ΔS
großartig aus — 63.3 gegen nur 31.2 (Median) bei BGR, also scheinbar der doppelt
so starke Kanal. Die Kontrolle entlarvt das: auf leerem schwarzem Bett liegt ΔS
schon bei **26.9**. Der Grund ist rechnerisch, nicht optisch: `S = (max−min)/max`,
und wo `max` klein ist, bläst Sensorrauschen die Sättigung auf. Das Verhältnis
von Signal zu Untergrund beträgt damit nur **2.4×** — der schlechteste aller
Kanäle. Auf hellem Bett ist ΔS dagegen sauber (13.3×).

Ohne die Kontrollmessung wäre genau hier die falsche Entscheidung gefallen.

### Was die Messung stattdessen zeigt

Der Signalabstand auf schwarzem Bett ist **nicht das Problem**: max\|ΔBGR\|
liefert dort 9.9×, ΔV sogar 12.8× über dem Untergrund. Das Problem ist der
**Schwellwert**. Er steht global auf 40, und auf schwarzem Bett liegt der Pfeil
im Median bei 31.2 — **nur 38 % der Pfeil-Pixel kommen darüber**, gegen 90 % auf
hellem Bett. Der Schwellwert wirft also nicht Rauschen weg, sondern Signal:
40 ist das Zehnfache des schwarzen Bett-Rauschens (4.1), aber unterhalb des
Pfeils selbst.

Damit ist auch [erkennung.md §5.10](done/erkennung.md#510-schwellwert-senken-um-das-schwarz-signal-zu-heben)
neu einzuordnen. Dort wurde der Schwellwert *global* gesenkt und es wurde
schlechter (40 und 20 gleichauf, 12 katastrophal) — daraus folgte „unterhalb von
40 steckt kein Pfeil-Signal, nur Rauschen". Die Messung sagt: das gilt für die
**hellen** Betten, den Surround und die Kanten, wo das Rauschen sitzt. Auf
schwarzem Bett steckt sehr wohl Signal unter 40. Ein global gesenkter
Schwellwert konnte das nie zeigen, weil er überall gleichzeitig lockert. **Nur
auf schwarzen Betten zu lockern ist nie getestet worden.**

Die helleren Pfeile (`cc`, `fh`, `pz-light`) haben dieses Loch nicht: 78 % über
Schwellwert auf schwarzem Bett, 83 % auf hellem — sie sind gleichmäßig sichtbar.
Ihr Einbruch ist lokaler (der weiße Flight auf beigem Bett), nicht flächig.

**Einschränkung.** Gemessen wurde nur an korrekt gescorten Würfen, weil nur dort
die Achse vertrauenswürdig ist. Die Stichprobe ist damit zu den einfacheren
Fällen hin verzerrt; bei den Fehlschlägen dürfte der Anteil unter dem
Schwellwert eher höher liegen.

### HSV: ja, aber nicht als Kanalwechsel

Die Hoffnung war, dass HSV das Problem löst, weil es bei der Kalibrierung mit
Rot und Grün gut funktioniert
([kalibrierung.md §2.1](done/kalibrierung.md#21-farbsegmentierung-im-hsv-raum)):
Helligkeit steckt im V-Kanal und ist vom Farbton getrennt, also überlebt ein
Schwellwert auf H und S wechselnde Beleuchtung, was er in BGR nicht tut.

Die Messung sagt: **als reiner Kanalwechsel trägt das hier nicht.** Für den
schwarz-auf-schwarz-Fall — den größten — ist S numerisch unbrauchbar (2.4×) und
H noch schlechter (1.5×). Der beste Kanal auf schwarzem Bett ist ΔV (12.8×),
also faktisch das, was die Pipeline mit `max|ΔBGR|` (9.9×) ohnehin schon nimmt.
Rot und Grün funktionieren bei der Kalibrierung, weil sie *kräftig gesättigt und
hell* sind; ein schwarzes Bett hat per Definition keinen belastbaren Farbton.

Was von HSV bleibt, ist der **zweite** Fall: weißer Flight auf beigem Bett. Dort
ist S sauber (13.3× auf hellem Bett) und trägt die Unterscheidung, die BGR
teilweise verfehlt. HSV gehört also dazu — aber als *Ergänzung für helle Betten*,
nicht als Ersatz für den bestehenden Kanal.

### Die Schwelle muss pro Bett ermittelt werden

Das ist der eigentliche Hebel, und deine Intuition „Schwelle pro Wurf" trifft
genau zu — nur ist die relevante Achse nicht der Wurf, sondern das **Bett unter
dem Pixel**. Ein Schwellwert von 40 ist auf hellem Bett angemessen und auf
schwarzem Bett zu streng: dort liegt das Rauschen bei 4.1, der Pfeil bei 31.2.

Wo die Betten liegen, sagt die Homographie exakt — dieselbe Information, die
`segment_at` schon fürs Scoring liefert. Der Schwellwert kann also **ortsabhängig**
gesetzt werden statt global, abgeleitet aus dem, was an dieser Stelle tatsächlich
gemessen wird.

Für den hellen Fall gilt dasselbe Prinzip auf dem S-Kanal, und dort ist eine
feste Grenze zusätzlich ausgeschlossen, weil die Bett-Sättigung über die 16
Setups um mehr als das Doppelte streut:

| Setup | beige S | Setup | beige S |
|---|---|---|---|
| cc_setup1 | 41.8 | pz_setup2 | 67.7 |
| pz-light_setup1 | 50.0 | pz_setup4 | 71.1 |
| pz-light_setup2 | 50.4 | tz_setup2 | 72.0 |
| cc_setup2 | 54.5 | pz_setup1 | 73.5 |
| tz_setup5 | 58.1 | pz_setup3 | 76.6 |
| pz-light_setup3 | 58.2 | tz_setup3 | 88.1 |
| tz_setup4 | 61.7 | tz_setup1 | 94.3 |
| | | fh_setup1/2 | 103.1 / 103.9 |

Der beige Wert eines Setups liegt also über dem *weißen* Flight eines anderen.
Eine feste Grenze ist damit ausgeschlossen — sie würde je nach Board entweder
alles oder nichts fangen.

**Die Referenz kommt vom Board selbst.** Die Homographie sagt exakt, wo die
beigen und die schwarzen Betten liegen. Also pro Frame dort abtasten, die zwei
Verteilungen bilden und die Schwelle relativ dazu setzen. Das Board kalibriert
seinen eigenen Farbreferenzpunkt, und der Parametersatz bleibt über Board-Alter,
Weißabgleich und Beleuchtung hinweg gültig — dieselbe Logik, mit der schon alle
Größen in Board-Millimetern statt in Pixeln definiert sind.

Für die Arbeit ist das die interessantere Aussage als ein empirisch getunter
Schwellwert: nicht „diese Farbe ist ein Pfeil", sondern „das ist nicht die
Farbe, die hier hingehört".

### Keine hartkodierten Pfeilfarben

Bewusste Randbedingung: das Verfahren darf **nicht** voraussetzen, dass Pfeile
eine bestimmte Farbe haben. Ein früherer Entwurf hier wollte den Flight positiv
über „weiß" identifizieren, statt über die Breite — das ist gestrichen. Es würde
das System auf ein Pfeil-Modell festlegen, und der nächste Satz Pfeile bricht
es wieder. Erlaubt ist nur die Aussage, dass ein Pixel **nicht** zu dem Bett
passt, auf dem es liegt.

### Umsetzung

Reihenfolge nach erwartetem Hebel, jeder Schritt einzeln gemessen:

1. **Ortsabhängiger Schwellwert.** Pro Frame die Betten über die Homographie
   abtasten und den Schwellwert an das lokale Rauschniveau koppeln statt global
   auf 40 zu lassen. Das adressiert den größten Fall (schwarz auf schwarz, 38 %
   der Pfeil-Pixel gehen derzeit verloren) und braucht keinen neuen Kanal.
   Vorsicht an den Bett-Grenzen: der Schwellwert darf nicht auf einer Drahtkante
   springen, sonst entsteht genau der Kanten-Effekt aus Schritt 2 in Grün.
2. **S-Kanal für helle Betten.** Als zusätzlicher Kanal in der Differenz, mit
   einer aus der Bett-Sättigung des Frames abgeleiteten Schwelle. Nur dort
   anwenden, wo das Bett hell genug ist, dass S belastbar ist — die
   Kontrollmessung liefert die Grenze.
3. Die Ausdehnung der Maske weiter vom Intensitätskanal bestimmen lassen (Lehre
   aus Schritt 2: Farbe entscheidet *was*, nicht *wie weit*).

**Erwartung.** Der größte offene Hebel — er greift die Fragmentierung an der
Wurzel an, statt ihre Folgen zu reparieren. Wenn der Pfeil als *ein* Blob
ankommt, werden Fusion, Anker-Wahl und Spitzen-Präzision alle gleichzeitig
einfacher. Zugleich ist es der Schritt mit dem größten Rückschlag-Risiko: eine
gelockerte Schwelle lässt auch mehr Rauschen durch, und Schritt 2 hat gezeigt,
wie schnell breite Fremdfragmente den ganzen Fit entführen.

### Ergebnis: das Risiko ist eingetreten, der zweite Teil trägt

Der Schritt zerfällt in seine beiden Hälften, und sie gehen in verschiedene
Richtungen — beides ausgemessen in [erkennung-blob.md §3](erkennung-blob.md#3-was-dieser-lauf-gemessen-hat).

**Ortsabhängiger Schwellwert: verworfen.** Vier Varianten (roh / mit
Seed-Hysterese / nur in der Scoring-Fläche / nur für dunkler werdende Pixel), je
drei Werte, **alle unter der Baseline von 218**, und in jeder Variante fällt die
Quote monoton mit der Lockerung — das Optimum ist jedes Mal „aus". Die dunklen
Pfeile gewinnen dabei genau das Erwartete (`pz` bis zu +6, 73 % → 83 %), die
Wolfram-Boards verlieren mehr. Die Ursache ist nicht der Wert, sondern die
Fläche: die Lockerung galt über die gesamte Suchfläche, und dort gewinnt ein
breites Fremdfragment die Anker-Wahl.

**S-Kanal auf hellen Betten: übernommen.** Als zweiter Kanal neben `max|ΔBGR|`,
mit einem Gate auf helle Betten (dieselbe Bett-Selbstkalibrierung) und
`ΔS > 30`: **218 → 222/285, 76.5 % → 77.9 %**, und **kein Board verliert**. Die
Kontrolle bei `ΔS > 45` reproduziert die Baseline pro Board exakt.

Die Erwartung „wenn der Pfeil als ein Blob ankommt, wird alles einfacher" bleibt
richtig — sie ist nur nicht über den Schwellwert zu erreichen. Der Arbeitsplan
dafür steht jetzt in [erkennung-blob.md §6](erkennung-blob.md#6-arbeitsplan).

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
aber den in [erkennung.md §6](done/erkennung.md#6-stand-der-messungen) dokumentierten
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
  [erkennung.md §5.3](done/erkennung.md#53-zwei-unabhängige-ellipsen-fits-statt-registrierung)
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
