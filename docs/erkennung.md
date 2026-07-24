# Pfeil-Erkennung

Dokumentation der serverseitigen Detektions-Pipeline: was sie tut, welche
OpenCV-Algorithmen dabei zum Einsatz kommen, warum sie so aufgebaut ist und
welche Ansätze auf dem Weg dorthin verworfen wurden. Baut auf der fertigen
Kalibrierung auf ([kalibrierung.md](kalibrierung.md)) — ohne Homographie kein
Scoring.

Referenz-Implementierung:
`backend/src/app/api/features/detection/services/dart_detector.py`.
Literatur-Sammelstelle: [roadmap.md §6.2](roadmap.md#62-pfeil-lokalisierung--verdeckung).

> **Stand:** Diese Pipeline ist neuer als die Kalibrierung und noch nicht auf
> ihrem Endstand. Es gibt inzwischen eine Ground-Truth-Evaluation (§6): aktuell
> **61.7 % korrektes Segment** über 60 Wurf-Paare, von einer 18.3 %-Baseline aus.
> Der Restfehler ist überwiegend Spitzen-Präzision beim schwarzen Pfeil (§6, §7).
> Das Dokument wächst mit.

---

## 1. Ziel und Ergebnis

**Eingabe:** drei Dinge —

1. ein **Referenz-Frame** (der letzte Frame, den das Board gezeigt hat),
2. ein **neuer Frame**, aufgenommen nachdem die client-seitige
   Frame-Differenz einen Wurf getriggert hat,
3. die **Kalibrierung des Referenz-Frames** (`Calibration`, aus der
   Board-Erkennung).

Beide Bilder liegen bei Client-Auflösung vor (max. Kantenlänge 1280 px,
JPEG q85), so wie sie auch die Kalibrierung bekommt.

**Ausgabe:** entweder ein `Dart` oder ein `DetectionFailure`.

```python
@dataclass(frozen=True)
class Dart:
    tip_image: tuple[float, float]                                   # Pixel
    axis_image: tuple[tuple[float, float], tuple[float, float]]      # Spitze, fernes Ende
    tip_board: tuple[float, float]                                   # Millimeter
    segment: Segment                                                 # z.B. T20 = 60
```

Die Bildkoordinaten liegen im Pixelraster des **Referenz-Frames**, nicht des
ankommenden — die Detektion richtet den neuen Frame vorher auf den Referenz-Frame
aus (§2.1), also teilen sich Overlay, Kalibrierung und Ergebnis dasselbe Raster.

### Das Grundprinzip: differenzieren, nicht wiedererkennen

Ein Pfeil ist ein schlechtes Detektionsziel *an sich*: dunkel, dünn, und er
landet auf einem Board, das ebenfalls überwiegend dunkel und von dünnen Drähten
durchzogen ist. Statt den Pfeil an seinem Aussehen zu erkennen, erkennt die
Pipeline **was der Wurf hinzugefügt hat**: die Differenz zweier Frames. Das ist
ein weit stärkeres Signal als die Erscheinung des Pfeils selbst.

Entscheidend ist, gegen **welchen** Frame differenziert wird: gegen den
**vorherigen Frame**, nicht gegen ein leeres Board. Damit heben sich bereits
steckende Pfeile auf. Verdeckung wird erst dann zum Problem, wenn ein neuer Pfeil
einen alten *verdeckt* — nicht schon, wenn drei nebeneinander stecken.

### Der rollende Referenz-Frame (Live-Pipeline)

`detect_dart` kennt nur „Referenz + neuer Frame". Woher der Referenz-Frame
zwischen den Würfen kommt, entscheidet `core/socket.py` über einen
`FrameStore` je Spiel:

- Bei erfolgreicher Kalibrierung wird der **Kalibrierungs-Frame** (das leere
  Board) als erster Referenz-Frame hinterlegt. Er sitzt bereits im Pixelraster,
  zu dem die Homographie gehört.
- Nach jedem gescorten Wurf rollt die Referenz auf die **ausgerichtete Kopie**
  dieses Frames weiter (nicht das Rohbild — sonst driftet die Referenz aus dem
  Kalibrierungs-Raster). Der nächste Wurf wird also gegen diesen differenziert.

So sieht die Pipeline pro Wurf immer nur genau den neu hinzugekommenen Pfeil.

**Grenze:** Werden die Pfeile aus dem Board gezogen (Rundenende), driftet dieses
Prinzip — die nächste Differenz zeigt das *Entfernen* dreier Pfeile als große
Änderung. Ein „Board geleert"-Signal existiert noch nicht (siehe §7).

---

## 2. Pipeline im Überblick

```
Referenz-Frame + neuer Frame + Kalibrierung
 └─ 1. Registrierung (ORB, board-maskiert)  → neuer Frame auf Referenz gewarpt
     └─ 2. Differenz + Schwellwert + Cleanup → Änderungsmaske (Fragmente)
         └─ 3. Fragment-Fusion (Flight-Anker)→ Pfeil-Pixel auf einer Geraden
             └─ 4. Hauptachse (PCA) + Spitze → Ende gegenüber dem Flight
                 └─ 5. Scoring               → Segment (via Homographie)
```

Alle Größen (Kernel, Flächen) werden in **Millimetern auf dem Board** definiert
und pro Frame über die Homographie in Pixel umgerechnet — so bleibt derselbe
Parametersatz bei jeder Kameradistanz gültig (Testset: 0.6–0.9 px/mm).

---

### 2.1 Registrierung: neuen Frame auf den Referenz-Frame ausrichten

```python
orb = cv2.ORB_create(4000)
# Deskriptoren nur innerhalb der Board-Region (Maske!)
matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
cv2.findHomography(source, target, cv2.RANSAC, 2.0)
```

Handkameras driften. Schon wenige Pixel Versatz überschwemmen die Differenz:
gemessen am Testset leuchtet eine *unregistrierte* Differenz über einen 25-px-
Kameraversatz **~117 000 Pixel** auf, wo der Pfeil selbst ein paar Hundert wert
ist. Vor dem Differenzieren wird der neue Frame deshalb per Homographie auf den
Referenz-Frame gewarpt.

**Warum die Features auf die Board-Region maskiert werden** (`_board_region`,
bis `_DETECTION_RADIUS_MM = 225 mm` hinaus): Board und Wand liegen in
**unterschiedlichen Tiefen**. Sobald die Kamera *translatiert*, gibt es keine
einzelne Homographie mehr, die beide Ebenen gleichzeitig abbildet. Ein
unmaskierter Fit rastet gern auf der (größeren, texturärmeren) Wand ein und
lässt das Board schief — die Maskierung ist so wichtig wie die Registrierung
selbst.

**Warum RANSAC die steckenden Pfeile aushält:** die schon im Board sitzenden
Pfeile sind hier echte Ausreißer (sie liegen in beiden Frames woanders), aber
eine Handvoll gegen mehrere Hundert Board-Features — das Testset liefert
**340–1200 Inlier** allein auf dem Board. RANSAC verwirft sie mühelos. Verlangt
werden mindestens `_MIN_ALIGNMENT_INLIERS = 40`.

Der Detektionsradius reicht bewusst über die Scoring-Grenze (170 mm) hinaus: ein
Pfeil im Surround muss *gefunden* werden, um als Fehlwurf gemeldet zu werden —
sonst ist er nicht von „kein Wurf" zu unterscheiden.

---

### 2.2 Differenz, Schwellwert und Bereinigung

```python
difference = cv2.absdiff(reference, aligned).max(axis=2)   # pro Kanal, dann max
_, mask = cv2.threshold(difference, 40, 255, cv2.THRESH_BINARY)
mask = cv2.bitwise_and(mask, region)                       # nur Board
mask = _drop_speckle(mask, pixels_per_mm)                  # Fläche < 3 mm²  weg
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)     # 3 mm, Lücken schließen
```

**Pro Kanal differenzieren, dann maxen — nicht erst zu Grau wandeln.** Ein
Pfeil-Barrel vor einem schwarzen Segment kann in der *Helligkeit* fast identisch
sein und sich trotzdem in der *Farbe* unterscheiden. Das Kollabieren auf Grau
würde genau das wegwerfen.

**Schwellwert 40 Grauwerte:** Sensorrauschen liegt bei 2–4, der Schwellwert also
weit darüber, aber niedrig genug, um einen dunklen Pfeil vor einem schwarzen
Segment noch zu fassen.

**Reihenfolge: erst Speckle, dann Schließen.** Umgekehrt würde das Schließen
verstreutes Rauschen zu Blobs verbinden, die groß genug wären, um die
Flächengrenze zu überstehen. Der Pfeil ist dunkel auf dunklem Board, seine
Silhouette kommt also in Bruchstücken an — die das Schließen (3 mm) wieder
zusammensetzt.

---

### 2.3 Fragment-Fusion: den Pfeil aus Bruchstücken zusammensetzen

Ein **schwarzer** Pfeil erzeugt in der Differenz nur dort Signal, wo er über
*helle* Board-Bereiche läuft — über schwarzen Segmenten ist er von der Scheibe
kaum zu unterscheiden (schwarz auf schwarz ≈ 0 in allen Kanälen, §6). Er kommt
also nicht als ein Blob an, sondern als **mehrere Fragmente entlang einer
Geraden**. „Größter Blob" (der frühere Ansatz, §5.8) warf den Rest weg und zog
die Spitze zu dem Fragment, das die helle Scheibe zufällig zeigte — oft in die
Board-Mitte.

Stattdessen werden die Fragmente zu einem Pfeil zusammengefügt (`_fuse_dart_fragments`):

1. **Alle** Komponenten ≥ `_MIN_FRAGMENT_AREA_MM2 = 5 mm²` behalten. Je Fragment:
   Schwerpunkt, Quer-Breite (über die eigene PCA), mittlere Diff-Helligkeit.
2. **Flight = Anker.** Das breiteste Fragment (Helligkeit bricht Gleichstand) —
   die Federn spreizen die Silhouette, Barrel und Schaft bleiben dünn. Das ist
   das zuverlässigste Merkmal, nicht das störendste.
3. **Am Flight verankerte Gerade.** Für jede Kandidaten-Richtung (Flight-eigene
   Achse + Flight→jedes Fragment) zählen, welche Fragment-Schwerpunkte im
   Quer-Toleranzband `_FUSION_PERP_TOL_MM = 4 mm` liegen; die Hypothese mit der
   größten überdeckten Länge gewinnt. Dieselbe Hypothese-und-zähle-Idee wie die
   Board-RANSAC der Kalibrierung — **eine Stimme pro Fragment**, damit der fette
   Flight die dünne Schaft-Richtung nicht überstimmt. Durch die Verankerung am
   Flight ist es deterministisch, ohne Zufalls-Sampling.
4. **Längen-Cap** (`_MAX_DART_LENGTH_MM = 90 mm`): nur Fragmente in Pfeillänge um
   den Flight zählen mit. Ohne das belohnt die Längen-Bewertung ein weit
   entferntes, zufällig kollineares Fragment (Rauschen, ein Schatten quer übers
   Board) und streckt die Gerade quer durchs Bild — die Spitze landet dann weit
   außerhalb der Scoring-Fläche. Dieser Cap war der größte Einzel-Hebel
   (setup1: 27 % → 67 %, §6).

Bleibt nach Fläche nichts übrig oder ist der zusammengefügte Pfeil kleiner als
`_MIN_DART_AREA_MM2 = 20 mm²` → `DetectionFailure.NO_CHANGE` (kein Wurf, oder der
Pfeil ist vor der Aufnahme wieder abgeprallt).

---

### 2.4 Hauptachse und Spitze

```python
mean, eigenvectors = cv2.PCACompute(points, mean=None, maxComponents=1)
```

PCA über die zusammengefügten Pfeil-Pixel liefert die Längsachse. Ihre beiden
Enden sind Spitze und Flight.

**Welches Ende ist die Spitze?** Das **gegenüber dem Flight**, und der Flight ist
das *breitere* Ende. Der frühere Ansatz nahm das *zentrumsnächste* Ende (§5.9) —
das stimmt zufällig für zentrale Würfe (der Flight zeigt nach außen), kippt aber
genau bei den steilen Fällen, für die das System gebaut ist: ein Pfeil hoch am
Board, dessen Flight perspektivisch über die Mitte zurücklehnt, wurde dann von
seinem Flight aus gescort und fälschlich als `MISS` außerhalb gemeldet. Die
Orientierung an der Pfeil-*Form* statt an der Board-Mitte behebt das.

Die Homographie gilt ohnehin nur für die Board-Ebene, in der die Spitze steckt —
Barrel, Schaft und Flight ragen heraus und sind projektiv nicht gültig. Statt des
einen äußersten Pixels werden die letzten `_TIP_SPAN_MM = 3 mm` gemittelt.

---

### 2.5 Scoring

```python
board_point = _to_board(homography, tip)      # Pixel -> mm
segment = segment_at(*board_point)            # reine Geometrie, board_geometry.py
```

Die Spitze wird durch die Homographie in Board-Millimeter abgebildet, dann
entscheidet `segment_at` rein geometrisch (Radius → Ring, Winkel → Sektor,
`board_geometry.py`). Jenseits von 170 mm ist das Ergebnis `MISS`.

---

## 3. Fehlerbehandlung

`detect_dart` gibt bei Misserfolg die **Stufe** zurück, die aufgegeben hat
(`DetectionFailure`) — wie `CalibrationFailure`, damit der Client dem Nutzer
einen konkreten Rat geben kann statt bloß „nichts gefunden".

| Failure | Bedeutung |
|---|---|
| `INVALID_IMAGE` | JPEG nicht dekodierbar |
| `NOT_CALIBRATED` | keine Kalibrierung / kein Referenz-Frame für dieses Spiel |
| `ALIGNMENT_FAILED` | Frames nicht in eine gemeinsame Sicht zu bringen — Kamera zu weit bewegt oder Board weitgehend verdeckt |
| `NO_CHANGE` | nichts Neues nahe dem Board — kein Wurf, oder Pfeil abgeprallt |

`INVALID_IMAGE` und `NOT_CALIBRATED` entstehen im Socket vor dem eigentlichen
Fit; `ALIGNMENT_FAILED` und `NO_CHANGE` im Detektor.

---

## 4. Debugging-Werkzeuge

**`DetectionTrace`** (`entity/detection_trace.py`) — reine Datenklasse, gleiche
Idee wie `CalibrationTrace`: `detect_dart` hält ohnehin Referenzen auf seine
Zwischenergebnisse, Aufzeichnen kostet also nichts und ist immer an. Bewusst
ohne Zeichenlogik.

**`dart_debug_images.py`** rendert den Trace als Bildfolge:

| Datei | Inhalt |
|---|---|
| `01_alignment.jpg` | Referenz rot, ausgerichteter Frame cyan — grau heißt, sie stimmen überein; farbige Säume an den Drähten = Registrierung schief (der Fehler, der überall zugleich einen Pfeil vortäuscht) |
| `02_difference.jpg` | rohe Differenz, gespreizt — beantwortet, ob der Pfeil nie in der Differenz war oder erst weggeschwellt wurde |
| `03_mask.jpg` | bereinigte Änderungsmaske über dem Frame |
| `04_components.jpg` | die Fragment-Fusion: verworfene Fragmente (grau), zusammengefügter Pfeil (grün), Flight-Anker (orange), gefittete Gerade (auf die Ausdehnung begrenzt). Gegen `02_difference.jpg` gehalten die Schlüsselansicht: wurden die verstreuten Fragmente korrekt auf eine Linie gefädelt, oder hat der Fit auf einem einzelnen hellen Fleck geankert? |
| `05_result.jpg` | gefittete Achse + gescorte Spitze |

**`scripts/detection/test_detection.py`** — läuft über Ordner von Wurfserien
(`<serie>_base.jpg`, `<serie>_dart1.jpg`, …), rekursiv durch Unterordner (die
Setups). Jedes aufeinanderfolgende Paar ist eine Detektion (`base → dart1`,
`dart1 → dart2`, …) — genau wie live, wo jeder Wurf gegen den vorigen Frame
differenziert wird. Standardmäßig durch die Client-Kette (Downscale, JPEG q85),
schreibt annotierte Kopien in eine gespiegelte `_results`-Struktur. Liegt in
einem Ordner eine `ground_truth.txt` (Zeilen `throw1_dart1 S5`), misst das Script
echte **Segment-Accuracy** und schreibt `_results/accuracy.md` mit einer
Mismatch-Liste; `--truth-template` bootstrappt diese Dateien aus den aktuellen
Detektionen.

**`scripts/detection/debug_detection.py`** — dasselbe für ein einzelnes
Referenz→Frame-Paar, mit vollem Bilder-Satz (`01`–`05`), um einen einzelnen
Fehlwurf Stufe für Stufe nachzuvollziehen.

---

## 5. Verworfene Ansätze

Dokumentiert, weil die Sackgassen für die Arbeit genauso relevant sind wie das
Ergebnis.

### 5.1 Erscheinungsbasierte Detektion (Hough-Linien / Kontur)

*Idee:* Der Konzept-Draft (konzept.md §3.2) sah „Pfeil-Detektion via
Konturanalyse oder Hough-Linien" auf dem Standbild vor — den Pfeil direkt an
seiner Gestalt erkennen.

*Warum verworfen:* Ein Pfeil ist dunkel und dünn auf einem Board voller dunkler,
dünner Drähte — das Aussehen ist ein schwaches Signal, und Hough-Linien fänden
ebenso die Sektordrähte. Die Frame-Differenz gegen den vorigen Zustand ist ein
ungleich stärkeres Signal, weil sie *nur* das Neue zeigt. Das ist der
grundlegende Richtungswechsel gegenüber dem Draft.

### 5.2 Differenz gegen das leere Board

*Idee:* Jeden Wurf gegen den kalibrierten Leerzustand differenzieren.

*Warum verworfen:* Dann leuchten **alle** aktuell steckenden Pfeile auf, nicht
nur der neue. Der „größte Blob" wäre nicht mehr eindeutig der neue Pfeil, und
bereits gezählte würden erneut detektiert. Gegen den *vorigen* Frame heben sich
alte Pfeile auf — nur der hinzugekommene bleibt übrig.

### 5.3 Zwei unabhängige Ellipsen-Fits statt Registrierung

*Idee:* Statt den neuen Frame zu warpen, jeden Frame einzeln kalibrieren und die
Board-Modelle vergleichen.

*Warum verworfen:* Zwei unabhängige Fits stimmen für eine Pixel-Differenz nicht
eng genug überein — am Testset drifteten die gefitteten Achsen zwischen zwei
aufeinanderfolgenden Frames einer Serie um **7 %**, genug, um jeden Draht des
Boards aufleuchten zu lassen. Deshalb wird der neue Frame auf den Referenz-Frame
registriert und beide teilen sich exakt dieselbe Kalibrierung.

### 5.4 Unmaskierte Registrierung (Features über das ganze Bild)

*Idee:* ORB-Features auf dem kompletten Bild statt nur auf dem Board.

*Warum verworfen:* Board und Wand liegen in verschiedenen Tiefen. Sobald die
Kamera translatiert, passt keine Homographie auf beide — der Fit rastet auf der
Wand ein und lässt das Board misaligned. Die Features werden deshalb auf die
Board-Region maskiert (§2.1).

### 5.5 Grauwert-Differenz statt Farbkanäle

*Idee:* Vor dem Differenzieren zu Grau wandeln (schneller, ein Kanal).

*Warum verworfen:* Ein Pfeil-Barrel vor einem schwarzen Segment ist in der
Helligkeit fast identisch, unterscheidet sich aber in der Farbe. Grau wirft das
weg. Deshalb `absdiff` pro Kanal, dann Maximum.

### 5.6 Morphologisches Opening gegen Speckle

*Idee:* Rauschen per `MORPH_OPEN` entfernen, wie es die Kalibrierung tut.

*Warum verworfen:* OpenCVs kleinstes brauchbares Strukturelement ist 3×3 — bei
0.6–0.9 px/mm sind das 3–5 mm, **breiter als der Pfeil**, den es erhalten soll.
Gemessen warf ein Opening **60 %** der Pfeil-eigenen Pixel weg. Komponenten
unter einer schlichten Flächengrenze (`_MIN_SPECKLE_AREA_MM2 = 3 mm²`) zu
verwerfen entfernt dasselbe Rauschen, ohne irgendetwas zu erodieren.

### 5.7 Der einzelne Extrempixel als Spitze

*Idee:* Das äußerste Achsen-Pixel direkt als Spitze nehmen.

*Warum verworfen:* Dieses eine Pixel ist, was der Schwellwert zufällig gefasst
hat — instabil. Über `_TIP_SPAN_MM = 3 mm` Achsenende gemittelt sitzt die Spitze
ruhig.

### 5.8 „Größter Blob" als Pfeil

*Idee:* Aus der Änderungsmaske schlicht die flächengrößte Komponente als Pfeil
nehmen.

*Warum verworfen:* Der schwarze Pfeil kommt fragmentiert an (§2.3). Der größte
Einzel-Blob ist dann nur das Stück, das über der hellsten Scheibenfläche lag —
meist nahe der Mitte — und zieht die Spitze dorthin. **Messbar:** dieser Ansatz
(mit der zentrumsnächsten Spitze, §5.9) war die **18.3 %-Baseline**; der Wechsel
auf Fragment-Fusion (§2.3) hob das auf **48.3 %**, der Längen-Cap auf **61.7 %**
(§6).

### 5.9 Das zentrumsnächste Ende als Spitze

*Idee:* Von den zwei Achsen-Enden das der Board-Mitte nähere als Spitze nehmen.
Begründung: Barrel/Schaft/Flight ragen aus der Ebene und werden weiter *außen*
abgebildet, das innere Ende sei also die Spitze.

*Warum verworfen:* Das gilt nur, solange der Flight nach außen zeigt. Bei einem
Pfeil hoch am Board lehnt der Flight perspektivisch über die Mitte zurück, das
zentrumsnächste Ende ist dann der Flight, und der Pfeil wird von seinem Flight
aus gescort (fälschlich `MISS`). Die Orientierung am *breiteren* Ende (dem
Flight, §2.4) ist formbasiert statt lagebasiert und behebt genau diese steilen
Fälle. Isoliert gemessen: **18.3 % → 21.7 %** (der Rest des Sprungs kommt aus der
Fusion, die beiden greifen ineinander).

### 5.10 Schwellwert senken, um das Schwarz-Signal zu heben

*Idee:* Wenn der schwarze Pfeil über schwarzen Segmenten kaum difft, dann eben
`_DIFFERENCE_THRESHOLD` senken, bis der Barrel sichtbar wird.

*Warum verworfen:* Negativergebnis. Auf setup1 gemessen: Threshold 40 und 20
ergaben identische **33.3 %**, Threshold 12 fiel auf **6.7 %**. Unterhalb von 40
steckt kein Pfeil-Signal, nur Rauschen, das den Blob korrumpiert. Wo schwarz auf
schwarz ≈ 0 Differenz erzeugt, holt kein Schwellwert etwas zurück — das ist der
Grund, warum das Modell (Fusion + Flight-Orientierung) den Weg trägt, nicht das
Front-End.

---

## 6. Stand der Messungen

Testdaten: vier Kamera-Setups (`setup1`–`setup4`), je fünf Wurfserien mit
Basisbild + drei Pfeilen = **60 Detektions-Paare**, verschiedene Winkel und
Distanzen (0.63–0.90 px/mm), schwarze Pfeile. Jeder Ordner trägt eine
`ground_truth.txt` mit dem tatsächlichen Segment je Pfeil (gegen die Videos
korrigiert). Gemessen bei Client-Auflösung mit `test_detection.py`.

### Genauigkeits-Verlauf

Jeder Schritt gegen dieselbe Ground Truth, damit die Verbesserung sichtbar ist:

| Schritt | Korrektes Segment |
|---|---|
| Größter Blob + zentrumsnächste Spitze (Baseline, §5.8/5.9) | 11 / 60 — **18.3 %** |
| + Flight-Orientierung der Spitze (§2.4) | 13 / 60 — **21.7 %** |
| + Fragment-Fusion (§2.3) | 29 / 60 — **48.3 %** |
| + Längen-Cap (§2.3) | **37 / 60 — 61.7 %** |

Endstand über die Setups ausgewogen: **60 – 67 %** je Setup. Ein Blob wird
praktisch immer gefunden (60/60 „lokalisiert") — die aussagekräftige Zahl ist das
korrekte *Segment*, nicht „irgendwo ein Pfeil".

### Was den Restfehler ausmacht

Von 23 verbleibenden Mismatches sind nur noch **4 echte `MISS`** (Spitze außerhalb
170 mm); der Rest sind **Nachbar-Sektor- oder Ring-Fehler** (z.B. `S8`→`S12`,
`S20`→`T20`) — die Spitze sitzt wenige Millimeter daneben. Ursache ist durchweg
das **farb-gegatete, fragmentierte Signal** des schwarzen Pfeils: er difft nur
über hellen Segmenten, über schwarzen ist er ≈ unsichtbar. Wo die Fusion nur ein
einzelnes Rand-Fragment fasst und das echte innere Signal unverbunden bleibt,
ankert der Fit falsch. Kein Schwellwert holt das zurück (§5.10) — der Deckel ist
das Front-End-Signal, nicht der Algorithmus.

Die Laufzeit pro Detektion ist noch nicht systematisch gemessen.

---

## 7. Offene Punkte

- **Signal statt Algorithmus — nicht-verblendende Pfeile.** Die stärkste offene
  Stellschraube ist das Front-End: schwarze Pfeile sind ein pathologischer Fall
  (§5.10, §6). Ein Setup mit helleren/reflektierenden Pfeilen oder besserer
  Ausleuchtung aufnehmen und dagegen messen — das isoliert, wie viel Restfehler
  Signal und wie viel Algorithmus ist, und ist als „Bedingungen, unter denen die
  Methode trägt" ein eigenständiges Ergebnis.
- **Spitzen-Präzision / Fragment-Ankerung.** Wo die Fusion auf dem falschen
  Fragment ankert, hilft ein besserer Anker (z.B. Kombination aus Breite,
  Helligkeit und Board-Radius) oder das kantenbasierte Front-End (strukturelle
  statt Intensitäts-Differenz), um mehr Schaft-Signal zu gewinnen.
- **3D-lite Extrapolation.** Mit Kamera-Intrinsics (einmalige Vorkalibrierung)
  liefert die Homographie die volle Pose (`H = K·[r₁ r₂ t]`); eine bekannte
  Pfeillänge auf der Bild-Geraden ließe sich dann exakt mit der Board-Ebene
  schneiden. Bricht die Kalibrierung nicht, baut auf ihr auf — Ausblick.
- **Gelernter Tip-Detektor.** Robustester Endzustand gegen schwarz-auf-schwarz;
  die Ground-Truth-Infrastruktur (§6) ist der erste Schritt zu Trainingsdaten.
- **Board-Clear / Re-Base.** Der rollende Referenz-Frame kennt kein Signal, wann
  die Pfeile gezogen werden. Für echtes Mehr-Runden-Spiel muss ein geleertes
  Board die Referenz neu seeden (z.B. erneutes `calibration_frame`).
- **Verdeckung.** Aktuell nur implizit gelöst (neuer Pfeil verdeckt alten →
  Problem; drei nebeneinander → kein Problem). Das Linien-Modell hilft bei
  Teilverdeckung mehr als ein Schwerpunkt-Ansatz, der explizite Umgang ist aber
  Phase-3-Thema.
- **Objektivverzeichnung** wird von der Homographie geerbt — derselbe
  Randfehler wie bei der Kalibrierung.
