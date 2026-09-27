# Board-Kalibrierung

Dokumentation der serverseitigen Kalibrierungs-Pipeline: was sie tut, welche
OpenCV-Algorithmen dabei zum Einsatz kommen, warum sie so aufgebaut ist und
welche Ansätze auf dem Weg dorthin verworfen wurden.

Referenz-Implementierung:
`backend/src/app/api/features/calibration/services/board_detector.py`.
Literatur-Sammelstelle: [roadmap.md §6.1](../../roadmap.md#61-board-erkennung--kalibrierung).

---

## 1. Ziel und Ergebnis

**Eingabe:** ein einzelnes JPEG-Standbild vom Client (max. Kantenlänge 1280 px,
JPEG-Qualität 85), das das Dartboard aus beliebigem Winkel zeigt.

**Ausgabe:** eine 3×3-**Homographie-Matrix**, die Bildpixel in
Board-Millimeter abbildet, plus die Bildabmessungen
(`Calibration(homography, image_width, image_height)`).

Alles Weitere — Scoring, Overlay, Heatmaps — baut ausschließlich auf dieser
Matrix auf. Die Kalibrierung ist damit der einzige Schritt, der die Kamera
überhaupt mit der genormten Board-Geometrie in Beziehung setzt.

### Das Board-Koordinatensystem

Definiert in `domain/board_geometry.py`, nach WDF/BDO-Norm:

| Größe | Wert |
|---|---|
| Bullseye (50) | r ≤ 6.35 mm |
| Bull (25) | r ≤ 15.9 mm |
| Triple-Ring | 97.4 – 107.4 mm |
| Double-Ring | 160.0 – 170.0 mm |
| Äußere Scoring-Grenze | 170.0 mm |
| Sektoren | 20, je 18° |

Ursprung im Bullseye, x nach rechts, y nach oben, Winkel gegen den Uhrzeigersinn
ab +x. Sektor 20 hängt konventionsgemäß oben (`FIRST_SECTOR_CENTRE_ANGLE = π/2`),
die Sektorfarben alternieren strikt, Sektor 20 ist rot.

**Ringbreite.** Die Norm fixiert die *Außenkante* (170.0 bzw. 107.4 mm, jeweils
bis zur Außenseite des Drahts) und die Breite getrennt: 8.0 mm inside-to-inside
bei Runddraht, 10.0 mm apex-to-apex bei Banddraht. Das ist derselbe Ring — bei
Runddraht liegen die fehlenden 2 mm unter den beiden Drähten, bei Banddraht sind
sie Sisal. Die Scoring-Bänder waren bis 20.09. mit 8.0 mm an die Außenkante
geklebt und damit innen 2 mm zu kurz; das war die häufigste Einzelursache für
Fehlwertungen ([testrun1 §3](../../test/testrun1.md#3-ring-innenkanten-nachmessen)).
Sie standen danach auf `RING_WIDTH = 9.2 mm`, ab 21.09. auf 9.8 mm und seit
27.09. auf den **10.0 mm** der Norm. Der Rest der gemessenen Abweichung ist kein
Geometrie-, sondern ein Kalibrierungsfehler und gehört nicht in diese Konstante
(siehe §7).

### Was die Homographie aussagt

Sie ist eine Abbildung **Ebene → Ebene** in homogenen Koordinaten:

```
[u]       [x]                 X = u/w
[v]  =  H [y]      dann       Y = v/w
[w]       [1]
```

Die Division durch `w` ist der entscheidende Teil: eine rein lineare Abbildung
bildet Parallelen immer auf Parallelen ab und kann deshalb keine perspektivische
Verkürzung darstellen. Erst das ortsabhängige `w` erzeugt sie.

`H` hat **8 Freiheitsgrade, nicht 9** — die Gesamtskalierung ist beliebig
(`H` und `2·H` beschreiben dieselbe Abbildung), deshalb wird auf `h₃₃ = 1`
normiert. Bei 2 Gleichungen pro Punktpaar reichen theoretisch **4
Korrespondenzen**; die Pipeline liefert 20, das System ist also überbestimmt.

Beispiel, gemessen an `pz-left-near.jpeg` bei Client-Auflösung (960×1280):

```
H = [[  0.980303  -0.085738  -555.451815 ]
     [  0.221028  -1.026905   213.261853 ]
     [ -0.000424   0.000370     1.0      ]]
```

- **Obere 2×2** — linearer Teil (Rotation, Skalierung, Scherung in einem).
  Determinante ≈ **-0.99**: Betrag nahe 1 heißt „ungefähr 1 mm pro Pixel",
  das negative Vorzeichen ist die Spiegelung, weil die Bild-y-Achse nach unten
  und die Board-y-Achse nach oben zeigt.
- **Dritte Spalte** `(-555.45, 213.26)` — Translation.
- **Untere Zeile** `(-0.000424, 0.000370)` — der perspektivische Teil. Sieht
  klein aus, wird aber mit Pixelkoordinaten im Tausenderbereich multipliziert.
  Über die vier Bildecken gemessen: `w` = 1.000 / 0.593 / 1.473 / 1.066, also
  **Faktor 2.5 zwischen den Extremen**. Genau das ist die Verkürzung.

Verifiziert: der Bull bildet auf (0.00, 0.00) mm ab, acht über die gefittete
Ellipse verteilte Punkte auf 169.8 – 170.2 mm.

Aus derselben Matrix lässt sich auch die Kamerapose zurückrechnen — daraus
entsteht der Blickwinkel, nach dem die Live-Auswertung aufschlüsselt
([auswertung.md §8](../auswertung.md#8-tracker-version-und-kamerawinkel)).

**Grenzen** (relevant für die Evaluation in Phase 4):

1. *Gilt nur für die Board-Ebene.* Die Pfeilspitze steckt in der Scheibe, passt
   also. Schaft und Flight ragen heraus und liegen außerhalb des
   Gültigkeitsbereichs — je flacher der Kamerawinkel, desto größer der
   Parallaxenfehler, wenn die Detektion versehentlich den Schaft lokalisiert.
2. *An die Kamerapose gebunden.* Sie verschmilzt Kamera-Intrinsics und
   Board-Pose zu einer einzigen Abbildung. Handy verschieben → ungültig.
3. *Kennt keine Objektivverzeichnung.* Eine Homographie ist projektiv,
   Tonnenverzeichnung eines Weitwinkel-Handyobjektivs ist es nicht. Der
   Restfehler wächst zum Bildrand hin. Die ±0.2 mm oben sind an genau den
   Punkten gemessen, aus denen `H` gefittet wurde — das ist das Fit-Residuum,
   keine unabhängige Genauigkeitsaussage.

---

## 2. Pipeline im Überblick

```
Bild
 └─ 1. Farbsegmentierung (HSV)              → rote/grüne Maske
     └─ 2. Board-Auswahl (Zwei-Ring-RANSAC) → nur Komponenten, die ein Board erklären
         └─ 3. Ellipsen-Fit (Convex Hull)   → äußere Kante des Double-Rings
             └─ 4. Ring-Walk                → Farbübergänge = Sektordrähte
                 └─ 5. Zuordnung            → 20 Punktkorrespondenzen
                     └─ 6. Homographie      → H, dann Mittelpunkt neu schätzen ↺
```

Schritte 4–6 laufen als **Iterationsschleife** (siehe §2.6).

---

### 2.1 Farbsegmentierung im HSV-Raum

```python
cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
cv2.inRange(hsv, lower, upper)
cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
```

Die roten und grünen Double-/Triple-Segmente sind das mit Abstand markanteste
Merkmal eines Boards und überstehen schlechte Beleuchtung deutlich besser als
Kanten.

**Warum HSV und nicht BGR:** Helligkeit steckt in HSV im V-Kanal und ist damit
vom Farbton getrennt. Ein Schwellwert auf H bleibt über wechselnde
Lichtverhältnisse hinweg brauchbar, während er in BGR mit jeder
Helligkeitsänderung mitwandern müsste.

**Rot braucht zwei Bereiche**, weil es am Ende der zyklischen Hue-Achse liegt
und umschlägt:

| Maske | Untere Grenze | Obere Grenze |
|---|---|---|
| Rot A | (0, 90, 60) | (10, 255, 255) |
| Rot B | (170, 90, 60) | (180, 255, 255) |
| Grün | (40, 60, 40) | (90, 255, 255) |

**Morphologie**, Kernel `cv2.MORPH_ELLIPSE` 5×5:

- `MORPH_CLOSE` (Dilatation → Erosion) schließt die dünnen Drahtlücken zwischen
  benachbarten Segmenten, die sonst jedes Segment in Bruchstücke zerlegen.
- `MORPH_OPEN` (Erosion → Dilatation) entfernt anschließend isolierte
  Einzelpixel-Sprenkel.

Reihenfolge ist wichtig: erst verbinden, dann säubern.

---

### 2.2 Board-Auswahl per Zwei-Ring-RANSAC

**Das Problem.** Die Farbmaske enthält systematisch mehr als das Board.
Beobachtet in den drei Testscheiben (`pz`, `fh`, `cc`):

- die **Nummern** rund um den Ring, häufig rot/grün gedruckt,
- **Branding** auf dem Surround (bei `cc` z. B. rote Dekorbögen sowie
  PDC- und BLADE‖6-Logos),
- **Raum-Clutter**: ein Holzstuhl, dessen warmes Braun in den roten Hue-Bereich
  fällt (ein einzelner Blob mit 19 027 px), warmes Kunstlicht, Möbel.

Ein Ellipsen-Fit über *alles* ist dagegen wehrlos: die Convex Hull ist eine
äußere Hülle, ein einziger Ausreißer zieht sie mit, und in einem
Least-Squares-Fit zieht **jeder** Punkt mit, keiner kann ignoriert werden.

**Der Ansatz: hypothetisieren statt fitten.** Statt eine Ellipse durch alle
Punkte zu legen, wird ein Board *vorgeschlagen* und gezählt, wie viele Punkte
zustimmen:

1. Maske mit `cv2.connectedComponentsWithStats` labeln, Komponenten unter
   20 px verwerfen.
2. Je Komponente einen **Schwerpunkt** (Centroid) berechnen, getaggt mit seiner
   Farbe (+1 rot, −1 grün).
3. 800 Iterationen: 5 Schwerpunkte ziehen (5 Punkte definieren eine Ellipse),
   `cv2.fitEllipse`, Stimmen zählen.
4. Die Hypothese mit den meisten Stimmen gewinnt; ihre Wähler bilden die
   bereinigten Masken.

Ausreißer müssen nie identifiziert werden — sie stimmen einfach nicht mit ab.

**Warum eine Stimme pro Komponente, nicht pro Pixel.** Die Triple-Segmente sind
flächenmäßig fetter als die Double-Segmente. Bei Pixel-Voting überstimmen sie
den Double-Ring, den sie eigentlich bestätigen sollen.

**Warum ein Zwei-Ring-Modell.** „Punkte liegen auf dieser Ellipse" ist als
Modell viel zu schwach: der Triple-Ring liefert fast so viele Punkte wie der
Double-Ring, und entartete Ellipsen-Splitter, die beide streifen, gewinnen. Eine
Kandidatin muss deshalb ein ganzes **Board** erklären — zwei konzentrische Ringe
im normierten Verhältnis:

```python
_DOUBLE_BAND = (160.0 + 170.0) / 2 / 170.0   # ≈ 0.971
_TRIPLE_BAND = ( 97.4 + 107.4) / 2 / 170.0   # ≈ 0.602
_BAND_TOLERANCE = 0.10
```

Die Zuordnung läuft über den **normierten elliptischen Radius ρ**: der Punkt
wird in das Eigensystem der Ellipse rotiert und durch die Halbachsen geteilt,
womit die Ellipse zum Einheitskreis wird. ρ = 1.0 heißt exakt auf der Ellipse.
Die Bänder liegen mittig im Ring, weil Segment-Schwerpunkte mittig liegen und
nicht auf der Außenkante.

**Strukturelle Tests, bevor Stimmen überhaupt zählen.** Jeder dieser Tests hat
einen konkreten Fehlfall behoben:

| Test | Parameter | Behobener Fall |
|---|---|---|
| Kandidatin nicht viel größer als das Bild | `_MAX_FRAME_SHARE = 1.2` | `cc-center-mid` Vollauflösung |
| Kandidatin kein Splitter | `_MAX_AXIS_RATIO = 4.0` | dito |
| Stimmen über ≥ 8 von 12 Winkelsektoren verteilt | `_MIN_ANGULAR_SECTORS` | `cc-center-near` Vollauflösung |
| Beide Bänder besetzt (≥ 6 Mitglieder) | `_MIN_BAND_MEMBERS` | — |
| Beide Bänder alternieren rot/grün (Minderheitsfarbe ≥ 25 %) | `_MIN_MINORITY_SHARE` | `cc-center-far` Vollauflösung |

Der letzte ist der wichtigste und beruht auf der einzigen Eigenschaft, die
Board von Clutter zuverlässig trennt: **alle Störquellen sind einfarbig**. Nur
Triple- und Double-Ring legen rot und grün abwechselnd nebeneinander. Die
Dekorbögen eines Surrounds bilden einen überzeugenden Ring — aber einen
einfarbigen.

Ein Kandidat, der einen Test reißt, bekommt **0 Stimmen**, nicht bloß weniger.

**Nachjustierung (`_settle_hypothesis`).** Die Siegerin stammt aus 5 zufällig
gezogenen Punkten: gut genug, um jede Rivalin zu schlagen, aber ungenau genug,
dass Segmente am Toleranzrand herausfallen. Ein fehlendes Double-Segment ist
später ein fehlender Farbübergang, und die Drahtzuordnung besteht auf allen
zwanzig. Also: auf den Double-Ring-Wählern neu fitten, um `1/_DOUBLE_BAND`
nach außen skalieren (der Fit sitzt ja mittig im Ring), neu einsammeln — bis zu
4 Durchgänge, Abbruch sobald es nicht mehr besser wird.

**Fremdkörper im Band (`_trim_band_strays`).** Die Bandtoleranz von 0.10 muss
locker sein, weil eine aus fünf Punkten gezogene Hypothese keinen festen Maßstab
hat. Damit stimmt aber auch das **Branding auf dem Zahlenring** mit ab: auf der
Blade 6 sind das der WINMAU-Schriftzug, die rote 6 von BLADE6 und die beiden
GEN⑥TEC-Plaketten — vier rote Blobs, knapp außerhalb des Double-Rings und
ringförmig über das Board verteilt, also genau in der Toleranz (ρ = 1.01 – 1.11).

Das ist deshalb fatal, weil der anschließende Hüllen-Fit (§2.3) durch die
**äußersten** Punkte läuft. Nimmt er das Branding mit, hängt die Ellipse daran —
und der Ausreißer-Test misst gegen ebendiese Ellipse. Der Ausreißer hat sie
gerade so weit aufgebläht, dass er selbst innen liegt (ρ ≈ 0.98 ≤
`_OUTER_BAND_LIMIT`), der Test sieht keinen Ausreißer mehr. Eine
selbstbestätigende Schleife: die Annahme „jede Runde schrumpft die Ellipse"
gilt nur, solange der Fit nicht schon am Ausreißer hängt.

Gemessen an einem exportierten Spiel (57 Frames, **feststehende Kamera**, also
eine einzige richtige Antwort): 11 Frames lieferten eine um **7.7 % zu lange**
Hauptachse — und alle 11 meldeten `OK` mit 20/20 Drähten. Eine stille
Fehlkalibrierung, die eine ganze Runde falsch wertet, ist schlimmer als ein
sauberer Fehlschlag.

Der Ausweg nutzt eine Zahl, die kein Fit verfälschen kann: **ein Ring hat genau
zwanzig Segmente**. Solange ein Band mehr Mitglieder hat, fliegt das
**äußerste** heraus, gemessen an einer Ellipse durch die Schwerpunkte des Bandes
selbst. Dass gerade das äußerste gehen muss und nicht das am schlechtesten
passende, ist die Invariante aus §2.3: Branding sitzt immer außerhalb des
Double-Rings, nie innerhalb.

| | vorher | nachher |
|---|---|---|
| Export, verschiedene Ellipsen auf 57 Frames | 2 Cluster, Δ Hauptachse 7.7 % | **eine, ± 1 px** |
| Testsatz erkannt | 15 / 18 | **15 / 18** |
| `cc-center-mid` Hauptachse | 253 px | **240 px** (farblose Ring-Proben 3 % → 2 %) |
| Segment-Accuracy der Detektion | 227 / 285 | **234 / 285** |

Der Zugewinn der letzten Zeile sitzt vollständig auf `pz` (45 → 50 / 60) und
`cc` (24 → 26 / 30) — den beiden Boards, auf denen die Verschmutzung überhaupt
gemessen wurde. `pz-light`, `tz` und `fh` bleiben auf den Pfeil genau gleich.

**Reproduzierbarkeit:** `np.random.default_rng(0)`. Ein Detektor, dessen Antwort
zwischen Läufen wackelt, lässt sich nicht debuggen.

---

### 2.3 Ellipsen-Fit über die Convex Hull

```python
cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cv2.convexHull(points)
cv2.fitEllipse(hull)
```

Unter Perspektive projiziert ein Kreis auf eine **Ellipse**. Der äußerste
farbige Ring ist die Außenkante des Double-Rings — Radius 170 mm, bekannt.

Die Convex Hull aller überlebenden farbigen Pixel zeichnet genau diese
Außenkante nach: der Ring ist zwar durch die schwarz/weißen Segmente
unterbrochen, aber die Hülle überbrückt diese Lücken.

`cv2.fitEllipse` implementiert Fitzgibbons Least-Squares-Verfahren und braucht
mindestens 5 Punkte. Rückgabe: `((cx, cy), (achse_a, achse_b), winkel)` —
Achtung, **volle** Achsenlängen, die Parameterform braucht Halbachsen.

**Nachbereinigung.** Clutter dicht am Board überlebt die RANSAC-Wahl
gelegentlich. Es sitzt aber immer weiter außen als der Double-Ring. Also: fitten,
jede Komponente mit ρ > 0.99 verwerfen, neu fitten. Ein Durchgang reicht nicht,
weil der erste Fit gerade wegen der Ausreißer zu großzügig ist; jede Runde
schrumpft die Ellipse und schiebt den Rest weiter nach außen, die Schleife
konvergiert also auf den Ring (max. 4 Durchgänge).

---

### 2.4 Ring-Walk: Farbübergänge finden

Nach dem Fit ist bekannt, dass **jeder** Punkt auf der Ellipse das Bild eines
Board-Punktes bei exakt 170 mm ist. Unbekannt ist nur noch, zu **welchem
Winkel** er gehört.

Naheliegend wäre, den Ellipsen-Parameter direkt als Board-Winkel zu nehmen. Das
ist **nur bei Parallelprojektion korrekt**. Bei den steilen Blickwinkeln, für die
das System gebaut ist, verschiebt es den Board-Mittelpunkt um zig Millimeter —
weit mehr als die 8 mm Breite eines Triple-Rings.

Stattdessen liefert die Farbe echte Korrespondenzen: Farben wechseln **exakt an
den Sektordrähten**, deren Board-Winkel bekannt sind.

**Ablauf** (`_walk_ring_colours`):

- 720 Schritte um die Ellipse (0.5° Auflösung, weit feiner als die 18°
  zwischen Sektoren).
- Je Schritt 20 Proben auf der **Geraden vom Board-Mittelpunkt nach außen**, bei
  Radiusanteilen 0.50 – 0.98.
- Mehrheitsentscheid → +1 rot, −1 grün, 0 unklar.

Dass entlang einer *Geraden* gesampelt wird, ist kein Zufall: eine Homographie
bildet Geraden auf Geraden ab. Wenn `centre` das Bild des Board-Mittelpunkts ist,
teilen sich alle Punkte dieser Geraden einen Board-Winkel — nur deshalb landen
die Farbübergänge auf den echten Drähten. Der Spann 0.50 – 0.98 fängt Triple-
*und* Double-Ring (beide tragen pro Sektor dieselbe Farbe); Proben auf den
schwarz/weißen Singles liefern schlicht keine Farbe.

**Übergänge** (`_find_colour_transitions`): Läufe von „unklar" zwischen zwei
Farben werden überbrückt, der Übergang auf ihren Mittelpunkt gesetzt — dort
sitzt der Draht, der sie verursacht hat.

**Fehlübergänge filtern** (`_drop_spurious_transitions`): Drähte liegen einen
ganzen Sektor auseinander. Alles deutlich näher ist ein Fleck fehlklassifizierter
Farbe (Reflex, Schattenkante) und tritt immer **paarweise** auf — rein und sofort
wieder raus. Beide Partner werden verworfen, damit die Restsequenz mit den echten
Drähten ausgerichtet bleibt.

---

### 2.5 Zuordnung zu Board-Winkeln

Die Drähte werden durch **Abzählen entlang der Sequenz** zugeordnet. Das geht nur
auf, wenn alle zwanzig gefunden wurden — deshalb:

```python
if len(transitions) != SECTOR_COUNT:
    return None   # CalibrationFailure.SECTOR_WIRES_UNCLEAR
```

Eine zu kurze oder zu lange Sequenz würde die Zuordnung stillschweigend
verschieben und das Board um einen Sektor verdreht kalibrieren. Eine
fehlgeschlagene Kalibrierung, die der Nutzer wiederholen kann, ist besser als
jeder künftige Wurf gegen ein falsch rotiertes Board.

**Zwei Ambiguitäten sind aufzulösen:**

1. *Welcher Übergang ist welcher Draht?* Der Ellipsen-Parameter läuft
   gegenläufig zum Board-Winkel, also sind die Kandidaten die 20 zyklischen
   Rotationen der umgekehrten Reihenfolge. Bewertet wird jede über die
   **Farb-Übereinstimmung**: Draht `w` trennt Sektor `w-1` von Sektor `w`, die
   Farbe hinter dem Übergang muss also zu `is_red_sector(w)` passen.
2. *Farbe alterniert alle zwei Sektoren* → zehn gleich gute Rotationen bleiben
   übrig. Entschieden per `_upright_penalty`: die Konvention, dass **Sektor 20
   oben hängt**. Gemessen wird, wie weit die gewählte Zuordnung das Board vom
   Bildschirm-„oben" (−π/2, da y nach unten wächst) wegkippt.

Zuerst entscheidet die Farbe allein; nur unter den Zuordnungen, die sie *nicht*
trennen kann, wählt die Aufrecht-Strafe. Sie kann nie einen Draht überstimmen.

#### Warum die Strafe über die Homographie gemessen wird

Ursprünglich nahm `_upright_penalty` **einen** Ellipsenpunkt — den Draht neben
der 20 — und verglich dessen Bildschirmwinkel `atan2` mit „oben". Das ist falsch,
sobald die Kamera seitlich steht: **wo ein Ringpunkt im Bild erscheint, ist nicht
die Richtung, die er auf dem Board hat.** Die Projektion dreht diesen scheinbaren
Winkel um zweistellige Grad, die zehn Kandidaten liegen aber nur 36° auseinander
— es reicht also, dass die *Nachbar*-Rotation aufrechter aussieht als die
richtige. Der Fehler ist dann nicht klein, sondern volle **zwei Sektoren**.

Gemessen an `pz-light_setup1` (Stativ weit seitlich, Achsenverhältnis der Ellipse
1.73):

die drei engsten der zehn Kandidaten (alle mit Farb-Übereinstimmung 1.00):

| Kandidat | Strafe alt (1 Draht) | Strafe neu (Homographie) |
|---|---|---|
| Offset 14 (**richtig**) | 13.6° | **0.8°** |
| Offset 16 (alt gewählt) | **9.5°** | 21.5° |
| Offset 18 | 34.3° | 43.5° |

Die alte Messung wählte 16 mit 4° Vorsprung — das Board war um 36° verdreht
kalibriert, die 12 galt als 20, und *jeder* Wurf in diesem Setup war falsch
(23 % Segment-Accuracy).

Die Lösung nutzt, was ohnehin schon existiert: Für jeden verbliebenen Kandidaten
wird dessen **eigene Homographie** gefittet und gefragt, wo der Board-Punkt
`(0, 170)` — die Richtung der 20, auf Ringradius, also innerhalb der gefitteten
Korrespondenzen und nicht extrapoliert — im Bild landet. Die Homographie kennt
die Perspektive bereits; die Verzerrung wird damit herausgerechnet statt
abgeschätzt. Der richtige Kandidat gewinnt jetzt mit 0.8° gegen 21.5°, also mit
Faktor 25 statt knapp zu verlieren.

Kosten: bis zu zehn zusätzliche `findHomography`-Fits pro Verfeinerungspass, à
**0.28 ms** bei 20 Punkten — gegen eine Gesamtkalibrierung von 370–590 ms nicht
messbar (Messreihe vorher/nachher lag innerhalb des Rauschens). Auf dem
gesamten Testset: **69.8 % → 74.7 %**, `pz-light_setup1` 23 % → 70 %, alle 15
anderen Setups unverändert auf die Detektion genau.

---

### 2.6 Homographie-Fit und Mittelpunkt-Iteration

```python
cv2.findHomography(image_points, board_points, cv2.RANSAC)
```

Jeder der 20 Punkte sitzt auf der Außenkante des Double-Rings, dessen Radius
bekannt ist — die Paare sind exakt, nicht genähert:

```python
board_points.append((170.0 * cos(board_angle), 170.0 * sin(board_angle)))
```

**Warum eine Schleife.** Der erste Durchgang schickt seine Strahlen vom
*Ellipsen-Mittelpunkt* aus. Perspektive verschiebt den aber gegenüber dem echten
Board-Mittelpunkt, die Drahtwinkel kommen also schief heraus. Jede Homographie
lokalisiert den Mittelpunkt besser als die vorige:

```python
point = np.linalg.inv(homography) @ np.array([0.0, 0.0, 1.0])
```

Neu sampeln von dort, wiederholen. Auf synthetischen Testframes schrumpft das
Residuum je Durchgang etwa um Faktor drei (17.5 → 6.1 → 2.1 → 0.5 mm
Worst-Case). Abbruch, sobald die Verschiebung < 0.5 px ist; Deckel bei 6
Durchgängen, damit ein oszillierendes Bild nicht ewig dreht.

---

## 3. Fehlerbehandlung

`detect_board` gibt bei Misserfolg die **Stufe** zurück, die aufgegeben hat
(`CalibrationFailure`, ein `StrEnum` aus `domain/calibration_failure.py`), nicht
bloß `None` — damit der Client dem Nutzer sagen kann, was er ändern soll. Das DTO
`CalibrationResult` trägt diesen Wert im Feld `failure` an den Client:

| Failure | Bedeutung |
|---|---|
| `ELLIPSE_FIT_FAILED` | zu wenig Farbe, oder keine Board-Hypothese überzeugend |
| `SECTOR_WIRES_UNCLEAR` | ≠ 20 Farbübergänge gefunden |
| `HOMOGRAPHY_FAILED` | `findHomography` lieferte nichts |

---

## 4. Debugging-Werkzeuge

**`CalibrationTrace`** (`debug/trace.py`) — reine Datenklasse.
`detect_board` hält Referenzen auf Zwischenergebnisse, die es ohnehin berechnet;
Aufzeichnen kostet also nichts und muss nicht eingeschaltet werden. Bewusst
*ohne* Zeichenlogik, damit OpenCV-Rendering aus dem Service herausbleibt.

**`debug/render.py`** rendert den Trace als Bildfolge:

| Datei | Inhalt |
|---|---|
| `01_masks.jpg` | rohe HSV-Masken |
| `02_components.jpg` | rot/grün = überlebt · **grau** = hat nicht für die Board-Hypothese gestimmt · **stahlblau** = hat gestimmt, lag aber außerhalb des Double-Rings |
| `03_hull_ellipse.jpg` | Convex Hull (magenta) + gefittete Ellipse (gelb) |
| `04_passN_wires.jpg` | Ring-Walk: Punktfarbe = Votum, blaue Ticks = Übergänge |
| `05_passN_correspondences.jpg` | Drahtzuordnung, Sektor 0 (die 20) markiert |
| `06_result.jpg` | finales Board-Modell zurückprojiziert |

`02_components.jpg` gegen `01_masks.jpg` gehalten beantwortet die zentrale
Debug-Frage: kam eine schiefe Ellipse von schlechter Segmentierung oder von
schlechter Filterung?

**`scripts/calibration/run_all.py`** — läuft über den kompletten Testdaten-Ordner,
spielt jedes Foto standardmäßig durch die Client-Kette (Downscale auf 1280 px,
JPEG q85) und schreibt annotierte Kopien. Löscht vorher alte Overlays, damit
keine Artefakte eines früheren Laufs stehenbleiben. Die Messwerte stammen aus
`detector.trace`, nicht aus einer Neuberechnung — letzteres war schon einmal
still aus dem Takt geraten und beschrieb die alte Pipeline.

**`scripts/calibration/run_debug.py`** — dasselbe für ein einzelnes Foto, mit vollem
Bilder-Satz. Denselben Trace liefert auch der Kalibrierungs-WebSocket auf
Anfrage, es lässt sich also live debuggen.

---

## 5. Verworfene Ansätze

Dokumentiert, weil die Sackgassen für die Arbeit genauso relevant sind wie das
Ergebnis.

### 5.1 Toleranz-Aufweitung beim Ellipsen-Fit

*Idee:* Ausreißer über einen Inlier-Radius abfangen (`ρ ≤ 1.08`).

*Warum es scheiterte:* Die störende Beschriftung sitzt bei ρ = 1.00 – 1.06. Der
Filter war **weiter als der Fehler, den er entfernen sollte** — ein reiner
No-Op. Kein Konzeptfehler, eine zu große Zahl. Heute steht die Grenze bei
`_OUTER_BAND_LIMIT = 0.99`.

### 5.2 Bicolour-Dichte als globaler Filter

*Idee:* Nur Board-Segmente haben die jeweils andere Farbe in unmittelbarer
Nachbarschaft. Also: für jede Komponente die Dichte andersfarbiger Pixel im
Umkreis messen und global schwellwerten.

*Warum es scheiterte:* Die Dichte fällt zum Board-Rand hin ab. Auf Nahaufnahmen
warf der Schwellwert den Double-Ring mit weg — `fh-center-near` behielt nur
9 von 21 Komponenten. Als Filter aufgegeben, das Prinzip lebt in der
Alternations-Bedingung des RANSAC-Votings weiter (dort *pro Band* statt global).

### 5.3 „Alternation ≈ 20 Wechsel pro Radius"

*Idee:* Auf einem festen Radiusanteil um den Kandidaten-Mittelpunkt laufen und
Farbwechsel zählen. Beim echten Board müssten es 20 sein.

*Warum es scheiterte:* Unter Perspektive driftet ein fester Radiusanteil vom
Ring weg. Die Abdeckung lag nur bei 20–50 %, der Zähler kam nie über 12 —
die Größe war schlicht nicht messbar. Der spätere Ring-Walk (§2.4) löst genau
das, indem er entlang der **Ellipse** statt eines Kreises läuft und über 20
Radien mittelt.

### 5.4 Einfache Nachbarschafts-Farbprüfung

*Idee:* Der leichtgewichtige Vorgänger des RANSAC — Komponente behalten, wenn
in der Nähe die andere Farbe vorkommt.

*Warum verworfen:* Funktionierte auf den Testdaten überall bis auf ein
`-far`-Bild und war zwischenzeitlich sogar bewusst wiederhergestellt. Fiel
endgültig, als eigene Kameratests zeigten, dass das Problem **auch auf
Nahaufnahmen** auftritt: die Prüfung ist rein lokal und weiß nichts von
Kreisform, sie kann Nummern-Beschriftung dicht am Ring nicht von Ring-Segmenten
unterscheiden.

### 5.5 Klassische Hough-Kreis-Detektion

*Idee:* `cv2.HoughCircles` direkt auf das Board.

*Warum nicht:* Ein schräg fotografiertes Board ist im Bild eine Ellipse, kein
Kreis. `HoughCircles` sucht per Definition Kreise. Eine Hough-Transformation für
Ellipsen bräuchte einen 5-dimensionalen Akkumulator und ist entsprechend teuer —
RANSAC über bereits segmentierte Komponenten kostet dagegen 800 Ellipsen-Fits
über einige Dutzend Punkte.

*Nebenbei:* Der naheliegende Einwand „Kreiserkennung statt Masken?" ist ein
Zirkelschluss nur zur Hälfte. Es braucht die Farbmasken als **Eingabe**, aber
die Kreis-/Ellipsen-Annahme darf danach als **Modell** dienen, um zu entscheiden,
welche Masken-Teile dazugehören. Genau das tut §2.2.

### 5.6 Festes enges Toleranzfenster nach dem Settling

*Idee:* Die 0.10 braucht nur die rohe Hypothese. Nach `_settle_hypothesis` ist
das Modell genauer, also ein zweites Einsammeln mit ±0.03 um die Bandmitte.

*Warum es scheiterte:* Die gesettelte Ellipse ist von denselben Fremdkörpern
**selbst mitgezogen** (Hauptachse 475 statt 451 px). Gegen sie liegt das
Branding bei ρ ≈ 0.98, mitten im engen Fenster, während echte Segmente der
Gegenseite auf 0.85 rutschen und herausfallen. Das Fenster wirft genau das
Falsche weg: 18 → 12 von 18 erkannt.

### 5.7 Abweichung vom Median des Bands

*Idee:* Statt gegen einen Nominalwert gegen den Median der Bandmitglieder
messen — der ist maßstabsfrei und damit unabhängig davon, durch welche Punkte
die Hypothese gezogen wurde.

*Warum es scheiterte:* Die Annahme „echte Segmente bilden einen engen Cluster"
stimmt nur, wenn die Hypothese gut sitzt. Wo sie das nicht tut, läuft ρ als
**glatter Gradient über den Winkel** — auf `pz-center_flash` von 0.873 bis
1.049, und die niedrigen Werte gehören zu Segmenten mit ganz normaler Fläche
(192 – 229 px). Streuung misst hier die Güte der Hypothese, nicht die
Verschmutzung. 13 / 18.

*Was davon bleibt:* die Erkenntnis, dass **kein** Radiuskriterium trägt, solange
es gegen eine Ellipse gemessen wird, die der Ausreißer mitbestimmt hat. Deshalb
entscheidet §2.2 über die Segmentanzahl statt über einen Radius.

### 5.8 Innerhalb der Anzahl den am schlechtesten passenden verwerfen

*Idee:* Bei mehr als zwanzig Mitgliedern das mit der größten Abweichung |ρ − 1|
zur Schwerpunkt-Ellipse verwerfen.

*Warum es scheiterte:* Bei ebendiesem Gradienten ist die Abweichung des
*innersten* echten Segments größer (−0.116) als die des Brandings (+0.059) — es
flog ein echtes Segment heraus, `cc-center-mid` verlor die Drahtzuordnung
(14 / 18). Der Fix ist eine Zeile: das **äußerste** verwerfen, nicht das am
schlechtesten passende. Branding sitzt außen, das ist die Invariante, auf der
schon §2.3 beruht.
---

## 6. Stand der Messungen

Testdaten: 13 Fotos, drei verschiedene Boards (`pz`, `fh`, `cc`), verschiedene
Winkel und Distanzen. Gemessen bei Client-Auflösung.

| | vorher | nachher |
|---|---|---|
| Erkannt | 8 / 13 | **10 / 13** |
| Drähte je erkanntem Bild | teils 2/20 | **20 / 20** durchgehend |
| Farblose Ring-Proben (`cc`) | 73 – 86 % | **1 – 7 %** |
| Laufzeit | — | ≈ 432 ms / Bild |

800 RANSAC-Iterationen genügen; 2000 und 4000 änderten am Ergebnis nichts.

**Verbleibende Fehlschläge:**

- `cc-center-far` — meldet jetzt ehrlich `ellipse_fit_failed` statt einer
  vorgetäuschten 6×22-Ellipse. Bewusst nicht weiter optimiert: die Kamera soll
  laut Konzept nah am Board stehen, die sehr weiten Aufnahmen sind kein
  Maßstab.
- Zwei stark unterbelichtete `.JPG`-Aufnahmen — 0.00 % Farbe in der Maske. Ein
  HSV-/Belichtungsproblem, von dieser Arbeit unberührt; gehört zum Thema
  Beleuchtungsvarianz (Phase 3).

**Lokale Verifikation:** Tests mit der eigenen Kamera laufen einwandfrei, der
Ellipsen-Fit sitzt.

---

## 7. Offene Punkte

- **Unabhängige Genauigkeitsmessung.** Die ±0.2 mm sind das Fit-Residuum. Für
  eine belastbare Zahl braucht es Punkte, die *nicht* in den Fit eingegangen
  sind — etwa bekannte Positionen auf dem Triple-Ring. Ein erster solcher Satz
  liegt vor: die Farbkanten von Triple und Double, über 60 Radien je Basisbild
  gemessen ([testrun1 §3](../../test/testrun1.md#3-ring-innenkanten-nachmessen)).
- **Radialer Bias nach innen.** Ebendiese Messung: die Außenkante, auf die
  gefittet wird, sitzt richtig (−0.4 mm), die Kanten weiter innen laufen um
  1.0 – 1.9 mm nach innen weg. Ein reiner Skalenfehler wäre am Rand am größten,
  dieser ist dort null — das Muster passt zu Objektivverzeichnung, die von einer
  Homographie nicht erfasst wird. Plausibler Grund: **alle 20 Korrespondenzen
  liegen auf einem einzigen Kreis** (170 mm), radial innerhalb davon ist die
  Abbildung durch nichts gestützt. Kandidaten: zusätzliche Korrespondenzen auf
  den Ring-Innenkanten, oder eine Kamera-Vorkalibrierung.
- **Keine Selbstprüfung des Ergebnisses.** Die Pipeline meldet `OK`, sobald sie
  zwanzig Drähte zuordnen konnte — ob die Homographie *stimmt*, prüft sie nicht.
  Die Fremdkörper-Fälle aus §2.2 kamen deshalb als saubere Erfolge zurück und
  verdarben still eine ganze Runde. Der Trim beseitigt diese Ursache, nicht die
  Lücke: eine verzogene Ellipse aus einem anderen Grund sähe genauso aus. Eine
  billige Prüfung liegt nahe — nach dem Fit vom Mittelpunkt nach außen laufen
  und sehen, ob die äußerste Farbkante auf 170 mm abgebildet wird; weicht sie
  ab, `CalibrationFailure` statt Ergebnis.
- **Beleuchtungsvarianz.** Die HSV-Grenzen sind fest. Unterbelichtete Aufnahmen
  fallen komplett durch (siehe §6).
- **Objektivverzeichnung.** Aktuell unmodelliert; siehe den radialen Bias oben,
  der der erste gemessene Hinweis darauf ist.
- **Re-Kalibrierung.** `H` gilt nur für eine feste Kamerapose. Ausgelöst wird
  sie inzwischen an jedem Rundenwechsel, auf Anforderung eines beliebigen
  Geräts im Raum und beim Beitritt einer Kamera, für die das Spiel noch keine
  Kalibrierung hat — etwa nach einer Revanche
  ([multi-device.md §5c](multi-device.md#5c-rekalibrierung-anfordern)).
  Was fehlt, ist das *Erkennen* einer Verschiebung zur Laufzeit — die Zahl dafür
  liegt bereits vor (`alignment_shift_px` aus der Detection-Registrierung), sie
  löst nur noch nichts aus.
