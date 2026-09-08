# Pfeil-Erkennung

Dokumentation der serverseitigen Detektions-Pipeline: was sie tut, welche
OpenCV-Algorithmen dabei zum Einsatz kommen, warum sie so aufgebaut ist und
welche Ansätze auf dem Weg dorthin verworfen wurden. Baut auf der fertigen
Kalibrierung auf ([kalibrierung.md](done/kalibrierung.md)) — ohne Homographie kein
Scoring.

Referenz-Implementierung:
`backend/src/app/api/features/detection/services/dart_detector.py`.
Literatur-Sammelstelle: [roadmap.md §6.2](../roadmap.md#62-pfeil-lokalisierung--verdeckung).
Was als nächstes geändert wird und warum:
[erkennung-verbesserungen.md](erkennung-verbesserungen.md).

> **Stand:** Diese Pipeline ist neuer als die Kalibrierung und noch nicht auf
> ihrem Endstand. Es gibt inzwischen eine Ground-Truth-Evaluation (§6): aktuell
> **79.3 % korrekte Wertung** über 285 Wurf-Paare (fünf Boards, 16 Setups),
> von einer 18.3 %-Baseline aus. Der Restfehler zerfällt in Spitzen-Präzision
> (knapp die Hälfte der Mismatches liegt unter 5 mm) und eine Handvoll
> struktureller Ursachen (§6, §7). Die strukturelle Hälfte hat eine gemeinsame
> Wurzel — der Pfeil kommt nicht als ein Blob an — und ein eigenes Dokument:
> [erkennung-blob.md](erkennung-blob.md). Dort ist sie seit §6.5 auch direkt
> gemessen und nicht mehr nur erschlossen: **nur ein Drittel der Pfeile erreicht
> die Auswertung als eine Komponente**, und die Quote fällt mit jeder weiteren.
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

**Board geleert:** Werden die Pfeile aus dem Board gezogen, gilt die rollende
Referenz nicht mehr — die nächste Differenz zeigte sonst das *Entfernen* dreier
Pfeile als große Änderung, und die Fusion ankert auf dem breitesten Fragment,
also womöglich auf der Silhouette eines gezogenen Pfeils. Das Signal dafür ist
der **Rundenwechsel**: `next_player` schickt allen Kameras ein
`calibration_requested`, die daraufhin einen frischen Frame kalibrieren und
damit die Referenz auf das leere Board neu setzen (siehe
[multi-device.md §5c](done/multi-device.md#5c-rekalibrierung-anfordern)).

Das setzt voraus, dass der Rundenwechsel *nach* dem Ziehen der Pfeile ausgelöst
wird — was er tut, wenn er bestätigt wird („Wurf bestätigen"). Steht die
Einstellung auf automatisches Weiterschalten, kommt er direkt nach dem dritten
Dart und damit zu früh; die Kalibrierung sieht dann ein Board mit drei Pfeilen.

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
mask = cv2.bitwise_and(mask, search)                       # Board + Suchrand
mask = _drop_speckle(mask, pixels_per_mm)                  # Fläche < 3 mm²  weg
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)     # 3 mm, Lücken schließen
mask = _drop_unanchored(mask, region, pixels_per_mm)       # muss das Board erreichen
```

**Vorher wird ausgeschlossen, was der Frame gar nicht gesehen hat.**
`cv2.warpPerspective` füllt jeden Referenz-Pixel, für den es im Quellframe keinen
gibt, mit Schwarz — und gegen eine nicht-schwarze Referenz gehalten sind das
200+ Graustufen, das Fünffache des Schwellwerts, als breiter Streifen am
Bildrand. Da die Fragment-Fusion (§2.3) auf dem *breitesten* Fragment ankert,
nimmt sie genau diesen Streifen für den Flight. Derselbe Warp auf ein weißes Bild
angewandt liefert die Maske der tatsächlich beobachteten Pixel; um wenige Pixel
erodiert (die Randpixel sind zwischen Bildinhalt und Füllwert interpoliert und
gehören zu keinem von beidem) wird sie in `search` hineingeschnitten.

Was davon *innerhalb* der Board-Region liegt, ist zusätzlich eine Aussage über
das Setup: Board-Fläche, aus der die Kamera zwischen den beiden Frames
herausgeschwenkt ist. Ein Pfeil, der dort landet, ist nicht zu sehen — das ist
etwas anderes als „nichts gefunden" und steht deshalb im Trace
(`unobserved_region`). Ebenso `region_clipped`: der Anteil der Board-Kontur, der
schon im Referenzbild außerhalb des Bildes liegt (bei `pz-light_setup3` sind das
30 % — ein Framing-Problem, das kein Algorithmus behebt).

Geschnitten wird gegen `search` (Detektionsradius + 90 mm), nicht gegen `region`:
der Flight eines hoch sitzenden Pfeils hängt über den Surround hinaus, und
abgeschnitten wäre er genau das Merkmal, das die Spitze orientiert (§2.4). Dass
eine Komponente *zum Board gehört*, prüft erst `_drop_unanchored` — nach dem
Schließen, damit über die ganze Silhouette entschieden wird und nicht über
einzelne Bruchstücke. Eine Komponente gilt als verankert, wenn sie in `region`
hineinreicht oder in Pfeillänge (`_MAX_DART_LENGTH_MM`) neben einer liegt, die
das tut — der zweite Fall ist der vom Schaft abgetrennte Flight.

**Pro Kanal differenzieren, dann maxen — nicht erst zu Grau wandeln.** Ein
Pfeil-Barrel vor einem schwarzen Segment kann in der *Helligkeit* fast identisch
sein und sich trotzdem in der *Farbe* unterscheiden. Das Kollabieren auf Grau
würde genau das wegwerfen.

**Zweiter Kanal: Sättigung, aber nur auf hellen Betten.** Ein weißer Flight über
einem beigen Bett unterscheidet sich in BGR um etwa 14 Grauwerte und ist damit
unsichtbar; in der Sättigung sind es rund 29. `absdiff` läuft deshalb zusätzlich
über den S-Kanal, verodert mit der Intensitätsmaske, Schwelle `_SATURATION_THRESHOLD = 30`.
Belastbar ist S nur, wo das Bett hell ist — über schwarzem Bett bläst
`S = (max−min)/max` das Sensorrauschen auf (Verhältnis 2.4× gegen 13.3× auf hellem
Bett). Wo ein Pixel zwischen den Betten steht, sagt das Board selbst: die
Homographie liefert die Mittelpunkte aller schwarzen und beigen Single-Betten
(`single_bed_centres`), dort wird die Referenz-Helligkeit gemessen, und der Kanal
zählt ab 60 % des Weges vom schwarzen zum beigen Niveau. Eine feste Grenze wäre
ausgeschlossen: die Bett-Sättigung streut über die 16 Setups um mehr als das
Doppelte. Messung: 218 → **222 / 285**, ohne Verlust auf irgendeinem Board.

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

1. **Alle** überlebenden Komponenten behalten. Je Fragment: Schwerpunkt,
   Quer-Breite (über die eigene PCA), mittlere Diff-Helligkeit. Zwei
   Flächengrenzen, nicht eine: unter `_MIN_SPECKLE_AREA_MM2 = 3 mm²` (bzw. 4 px,
   je nachdem was größer ist) fliegt eine Komponente ganz raus, unter
   `_MIN_CANDIDATE_AREA_MM2 = 10 mm²` (bzw. 15 px) darf sie den Fit weder
   verankern noch über seine Richtung abstimmen. Ihre Pixel zählen aber mit,
   sobald die Richtung steht — die Spitze selbst ist ein kleines Fragment, und
   sie wegzuwerfen verkürzt die Achse genau am falschen Ende.
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
4. **Längen-Cap** (`_MAX_DART_LENGTH_MM = 110 mm`): nur Fragmente in Pfeillänge um
   den Flight zählen mit. Ohne das belohnt die Längen-Bewertung ein weit
   entferntes, zufällig kollineares Fragment (Rauschen, ein Schatten quer übers
   Board) und streckt die Gerade quer durchs Bild — die Spitze landet dann weit
   außerhalb der Scoring-Fläche. Dieser Cap war der größte Einzel-Hebel
   (setup1: 27 % → 67 %, §6).

   Der Wert ist nach oben genauso heikel wie nach unten. Er stand zunächst auf
   90 mm, mit der Begründung, die sichtbare Ausdehnung eines Pfeils verkürze
   sich perspektivisch — das hat **das falsche Vorzeichen**: der Flight ragt aus
   der Board-Ebene zur Kamera hin heraus und wird von der Homographie deshalb
   *vergrößert* abgebildet. Korrekt gewertete Pfeile spannen im Testset bis
   148 mm. Bei 90 mm fielen Schaft und Barrel aus der Reichweite und die Achse
   lag durch den Flight allein. Gemessen über die 285 Paare: 90 → 222,
   **110 → 227**, 130 → 227, 150 → 219, 180 → 217 — ein Optimum im Inneren, und
   der Grund, warum 110 und nicht mehr. Aufschlüsselung in
   [erkennung-blob.md §6.1b](erkennung-blob.md#61b-fusions-reichweite-der-deckel-war-zu-eng).

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
einen äußersten Pixels wird über die letzten `_TIP_SPAN_MM = 4 mm` gemittelt, und
zwar **nur quer zur Achse**: entlang der Achse bleibt das Extremum stehen. Würde
man auch längs mitteln, zöge das die Spitze um eine halbe Bandbreite nach innen,
weil jedes Pixel des Bandes innerhalb des Extremums liegt. Die Glättung sitzt so
dort, wo sie hilft — bei der seitlichen Lage, die den Sektor entscheidet — ohne
den Pfeil zu verkürzen.

Welches Ende das breitere ist, wird über ein eigenes, breiteres Band gemessen
(`_FLIGHT_SPAN_MM = 12 mm`, 90. Perzentil der Querabstände), damit ein paar
Streupixel die Orientierung nicht kippen.

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
(`DetectionFailure`, ein `StrEnum` aus `domain/detection_failure.py`) — wie
`CalibrationFailure`, damit der Client dem Nutzer einen konkreten Rat geben kann
statt bloß „nichts gefunden". Das DTO `DetectionResult` trägt den Wert im Feld
`failure` an den Client.

| Failure | Bedeutung |
|---|---|
| `INVALID_IMAGE` | JPEG nicht dekodierbar |
| `NOT_CALIBRATED` | keine Kalibrierung / kein Referenz-Frame für dieses Spiel |
| `ALIGNMENT_FAILED` | Frames nicht in eine gemeinsame Sicht zu bringen — Kamera zu weit bewegt oder Board weitgehend verdeckt |
| `NO_CHANGE` | nichts Neues nahe dem Board — kein Wurf, oder Pfeil abgeprallt |
| `IMPLAUSIBLE_SHAPE` | etwas hat sich geändert, ist aber viel zu groß für einen Pfeil — jemand steht vor dem Board |

`INVALID_IMAGE` und `NOT_CALIBRATED` entstehen im Socket vor dem eigentlichen
Fit; die übrigen drei im Detektor.

`IMPLAUSIBLE_SHAPE` ist bewusst von `NO_CHANGE` getrennt, obwohl beide „kein
Pfeil gefunden" heißen: `NO_CHANGE` bedeutet, dass der Wurf null Punkte wert war
(siehe unten), `IMPLAUSIBLE_SHAPE` dagegen, dass das Bild überhaupt keinen Wurf
zeigte. Nur das erste darf je als Null gebucht werden.

### `NO_CHANGE` ist eine eigene Ground Truth

Ein Pfeil, der das Board getroffen hat und wieder herausgefallen ist, und ein
Pfeil im Surround sind punktemäßig dasselbe: null. Als *Detektionsaufgabe* sind
sie es nicht. Im ersten Fall ist nichts zu sehen und `NO_CHANGE` die richtige
Antwort; im zweiten steckt ein Pfeil im Bild, den die Pipeline finden soll.

Anfangs trugen beide das Label `MISS`, und `run_all.py` zählte ein `NO_CHANGE`
dagegen als korrekt. Das gab einer verpassten Detektion einen Treffer, sobald
der Pfeil zufällig außerhalb der Wertung steckte — nachgesehen an den drei
betroffenen Paaren traf das auf eines zu (`pz-light_setup1/throw8/dart2`: der
Pfeil ist im Bild sichtbar, am rechten Rand angeschnitten, r ≈ 214 mm).

Deshalb gibt es jetzt **zwei Labels**:

| Label | Bedeutung | Richtige Antwort |
|---|---|---|
| `NO_CHANGE` | im Bild ist kein neuer Pfeil | `NO_CHANGE` |
| `MISS` | Pfeil steckt, aber außerhalb der 170 mm | die Spitze lokalisieren |

`ALIGNMENT_FAILED` zählt nie mit — das ist kein Ablesen des Boards, sondern die
Unfähigkeit, überhaupt hinzusehen.

**Nicht dasselbe wie die Live-Wertung.** Im Spiel darf `NO_CHANGE` *nicht* blind
als null Punkte gebucht werden: die client-seitige Frame-Differenz ist auf Recall
ausgelegt und löst auch ohne Wurf aus. Ein automatisch gebuchter Nullwurf wäre
dann ein Phantom-Pfeil, der eine Aufnahme verbraucht. Der Detektor kann „Wurf
fand statt, blieb aber nicht stecken" nicht von „es gab keinen Wurf"
unterscheiden — diese Unterscheidung muss vom Client kommen (Arbeitsplan in
[client-diff-verbesserungen.md](client-diff-verbesserungen.md)).

Die Live-Auswertung zählt ein `no_change` dagegen immer als `missed`, auch bei
leerem Board ([auswertung.md §3a](auswertung.md#3a-die-gelesene-null-zählt-nicht)).
Das ist kein Widerspruch, sondern eine andere Frage: offline wird gemessen, ob
die Pipeline das Frame-Paar richtig *gelesen* hat, live, ob das System selbst
*gewertet* hat. Bei leerem Board hat es richtig gelesen und trotzdem nichts
gewertet — die Null kam von Hand.

---

## 4. Debugging-Werkzeuge

**`DetectionTrace`** (`debug/trace.py`) — reine Datenklasse, gleiche
Idee wie `CalibrationTrace`: `detect_dart` hält ohnehin Referenzen auf seine
Zwischenergebnisse, Aufzeichnen kostet also nichts und ist immer an. Bewusst
ohne Zeichenlogik.

**`debug/render.py`** rendert den Trace als Bildfolge:

| Datei | Inhalt |
|---|---|
| `01_region.jpg` | wo die Pipeline überhaupt suchen darf: Seed-Radius (gelb), Suchradius (orange), Board-Fläche die dieser Frame nicht abgedeckt hat (magenta), plus eine Warnzeile, wenn das Board aus dem Bild ragt |
| `02_alignment.jpg` | Referenz rot, ausgerichteter Frame cyan — grau heißt, sie stimmen überein; farbige Säume an den Drähten = Registrierung schief (der Fehler, der überall zugleich einen Pfeil vortäuscht) |
| `03_difference.jpg` | rohe Differenz, gespreizt — beantwortet, ob der Pfeil nie in der Differenz war oder erst weggeschwellt wurde |
| `04_threshold.jpg` | alles über dem Schwellwert, vor jeder Bereinigung. Das Rohmaterial: ist der Pfeil hier schon Krümel, liegt es am Schwellwert, ist er hier ein Streifen und später Krümel, an der Bereinigung |
| `05_cleanup.jpg` | was die Bereinigung verworfen hat und warum — rot: unter der Flächengrenze, blau: erreicht das Board nie, grün: behalten |
| `06_mask.jpg` | die bereinigte Änderungsmaske für sich, ohne Board darunter |
| `07_components.jpg` | die Fragment-Fusion: außer Reichweite (dunkelgrau), abgelehnt (hellgrau), zusammengefügter Pfeil (grün), Flight-Anker (orange), gefittete Gerade. Gegen `03_difference.jpg` gehalten die Schlüsselansicht: wurden die verstreuten Fragmente korrekt auf eine Linie gefädelt, oder hat der Fit auf einem einzelnen hellen Fleck geankert? |
| `08_axis.jpg` | welches Ende für den Flight gehalten wurde, mit beiden Breiten in Pixeln — die einzige Ansicht, in der eine knappe Entscheidung als knapp erkennbar ist |
| `09_result.jpg` | gefittete Achse + gescorte Spitze |

**`scripts/detection/run_all.py`** — läuft über Ordner von Wurfserien
(`<serie>_base.jpg`, `<serie>_dart1.jpg`, …), rekursiv durch Unterordner (die
Setups). Jedes aufeinanderfolgende Paar ist eine Detektion (`base → dart1`,
`dart1 → dart2`, …) — genau wie live, wo jeder Wurf gegen den vorigen Frame
differenziert wird. Standardmäßig durch die Client-Kette (Downscale, JPEG q85),
schreibt annotierte Kopien in eine gespiegelte `_results`-Struktur. Liegt in
einem Ordner eine `ground_truth.txt` (Zeilen `throw1_dart1 S5`), misst das Script
echte **Segment-Accuracy** und schreibt `_results/accuracy.md` mit einer
Mismatch-Liste; `--truth-template` bootstrappt diese Dateien aus den aktuellen
Detektionen.

Jedes annotierte Bild trägt zusätzlich das **Board-Modell**, das die Homographie
impliziert (Ringe + Sektordrähte, in cyan, aus `board_overlay.build_overlay`).
Das ist der Unterschied zwischen einer Sichtprüfung und einem Ratespiel: sitzt
die Spitze ein Segment daneben, ist das ein Kalibrierungsfehler, wenn die cyan
Ringe *neben* den echten liegen, und ein Detektionsfehler, wenn sie *auf* ihnen
liegen. Ohne das Modell im Bild sehen beide gleich aus. Dazu die gemessene
**Kamerabewegung** zwischen den beiden Frames (`trace.alignment_shift_px`), die
sich ebenfalls nicht ansehen lässt.

Jeder Mismatch trägt eine Spalte **`off by`**: der Abstand in Millimetern von der
gescorten Spitze zum nächstgelegenen Punkt des *erwarteten* Segments
(`distance_to_segment` in `board_geometry.py`, exakt gegen Ring-Radien und
Sektor-Keil gerechnet, `0` wenn die Spitze drin liegt). Das trennt die zwei
Fehlerarten, die in einer reinen Label-Liste gleich aussehen: **wenige
Millimeter** heißt, die Pipeline lag im Kern richtig und ist nur auf der falschen
Seite eines Drahts gelandet — Sub-Pixel-Präzision der Spitze, tolerierbar.
**Zig Millimeter** heißt, etwas Grundlegenderes stimmt nicht (Kalibrierung,
Alignment, falscher Blob) und ist kein Präzisionsproblem. Sortiert wird nach
Abstand aufsteigend, damit die plausiblen Fälle oben stehen; darüber steht, wie
viele Mismatches innerhalb von 5 mm liegen.

Dazu der Abschnitt **Per blob cohesion**: aus wie vielen Komponenten der
gewertete Pfeil zusammengesetzt werden musste, aufgeschlüsselt gegen die Quote.
Das misst das Ziel aus [erkennung-blob.md §1](erkennung-blob.md#1-die-ausgangsthese)
direkt — „eine Detektion = eine Komponente" — statt es aus der Segment-Quote zu
erschließen, die von zu vielem anderen abhängt. Aktuell erreichen **96 von 280**
Pfeilen (34 %) die Auswertung als ein Stück, und die Quote fällt von 81 % bei
einer Komponente auf 69 % bei drei bis vier.

**`scripts/detection/run_debug.py`** — dasselbe für eine einzelne Wurfserie, mit
vollem Bilder-Satz (`01`–`09`, Tabelle oben) je Pfeil, um einen Fehlwurf Stufe für
Stufe nachzuvollziehen. Argument ist die Serie (`pz_setup1/throw1`, oder bloß
`throw1`, wenn eindeutig); die drei Paare werden verkettet wie live, und jeder
Pfeil bekommt seinen eigenen Unterordner:

```
_results_debug/pz_setup1/throw1/dart1/01_region.jpg …
                               /dart2/…
                               /dart3/…
```

Je Pfeil steht zusätzlich eine **Fusions-Zeile** in der Konsole — wie viele
Komponenten es überhaupt gab, wie viele davon in Reichweite lagen und gefused
wurden, welchen Anteil die größte hält, und wie groß der Blob geworden ist:

```
dart1  S17 = 17   fused 2 of 2 components (2 in reach), largest holds 77% of the blob, blob 146 x 41 mm
```

Das ist genau die Ansicht, die `07_components.jpg` gibt, nur ohne ein Bild öffnen
und graue Flecken zählen zu müssen — und die Zeile, an der die zu enge
Fusions-Reichweite aufgefallen ist (§2.3).

Zwei Pfade als Argumente laufen weiterhin nur dieses eine Referenz→Frame-Paar.

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

### 5.5 Grauwert-Differenz statt Farbkanäle  *(inzwischen gemessen)*

*Idee:* Vor dem Differenzieren zu Grau wandeln (schneller, ein Kanal).

*Warum verworfen:* Ein Pfeil-Barrel vor einem schwarzen Segment ist in der
Helligkeit fast identisch, unterscheidet sich aber in der Farbe. Grau wirft das
weg. Deshalb `absdiff` pro Kanal, dann Maximum.

*Nachträglich belegt* über die Variante ΔV = `|max(B,G,R)_ref − max(B,G,R)_neu|`
(§5.14). Das Argument war ursprünglich nur plausibel; es ist jetzt eine Zahl.

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
hat — instabil. Über `_TIP_SPAN_MM = 4 mm` Achsenende quer gemittelt sitzt die
Spitze ruhig.

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

### 5.11 Gradientenabhängiger Schwellwert gegen Registrierungs-Reste

*Idee:* Die Registrierung ist nie pixelgenau, und was übrig bleibt, verteilt sich
nicht gleichmäßig: eine Verschiebung um δ ändert einen Pixel um etwa **|∇I|·δ**.
Ein flaches Bett (∇I≈0) bleibt ruhig, ein Draht oder eine gedruckte Zahl schlägt
um zig Graustufen aus — und diese Reste sind breit, hell und am Rand, also genau
das, was die Fragment-Fusion für einen Flight hält. Also den Schwellwert
mitwachsen lassen: `40 + Toleranz · |∇Referenz|`.

Der Zusammenhang ist belegt (`pz-light_setup2/throw5/dart1`, Suchbereich ohne den
Pfeil, 341 246 px): die mittlere Differenz steigt vom untersten Gradienten-Dezil
(0.6) zum obersten (12.4), und die Pixel über einem flachen Schwellwert von 40
haben im Mittel einen Gradienten von 52 Graustufen pro Pixel. Nach Helligkeit
sortiert gibt es keinen vergleichbaren Trend, und die beiden Frames unterscheiden
sich global nur um 1.4 % — es ist Verschiebung, keine Belichtung. **Nicht** aber
Kamerawackeln: der gemessene Versatz beträgt hier 0.2 px, der Rest ist *lokal*
(JPEG, Objektivverzeichnung, Tiefenunterschied Board/Surround).

*Zwei Varianten gemessen:*

1. **Direkt damit schwellen.** 218 → 173 von 285 (**76.5 % → 60.7 %**), bei
   gleichzeitig *besseren* Abständen (Mittel 35.3 → 25.3 mm, Maximum 220 → 135 mm)
   und mehr Fällen unter 5 mm (32 → 51). Die strukturellen Ausreißer verschwinden,
   aber der Pfeil verliert Pixel: seine **Spitze** ist klein, kontrastarm und liegt
   oft direkt neben einem Draht — genau dort, wo der Schwellwert angehoben wird.
   Eine verkürzte Achse setzt die Spitze auf die falsche Seite eines Rings.
2. **Als Seed-Kriterium** (Canny-Hysterese-Idee): der flache Schwellwert baut die
   Maske und bestimmt die Ausdehnung, der strenge erzeugt eine Seed-Maske, und
   eine Komponente wird nur geglaubt, wenn ≥ 25 % ihrer Pixel darin liegen. Ein
   Draht ist auf ganzer Länge Kante und fliegt ganz raus; ein Pfeil liegt auf
   flachem Bett, übersteht und behält seine volle Ausdehnung. Das funktioniert:
   218 → **221 (77.5 %)**, >50 mm-Fälle von 18 auf 13, Maximum 220 → 167 mm.
   `pz-light_setup3/throw7/dart1` ging von 74 Komponenten auf 4 und von `MISS`
   (220 mm daneben) auf das korrekte `S7`.

*Warum trotzdem verworfen:* drei Pfeile über 285 Paare sind zu wenig für den
Preis. Der Gewinn kommt ausschließlich von den Boards *mit* strukturellen
Fehlern (`tz` +2, `pz` +2, `pz-light` +1); **`fh` verliert zwei** und `cc` steht
still. Beide hatten vorher *null* Mismatches über 20 mm (mittlere Abweichung 4.2
bzw. 3.4 mm) — dort gibt es nichts zu gewinnen, und `fh` ist zugleich das
dunkelste Setup (Bett-Helligkeit 171–176 gegen 225 bei `pz-light`), sodass eher
eine echte Pfeil-Komponente unter den Seed-Anteil rutscht. Ein Verfahren, das auf
schwach ausgeleuchteten Aufnahmen Genauigkeit kostet, ist für unbekannte Setups
das falsche Risiko.

Als Bedingung formuliert und damit ein eigenständiges Ergebnis: **das Gate hilft
nur, wo das Front-End-Signal stark genug ist, dass Kanten-Residuen die einzige
Verwechslungsgefahr sind.** Bei schwachem Signal überwiegt der Verlust.

*Nebenbefund:* Komponenten, die in die Scoring-Fläche (170 mm) reichen, vom
Seed-Test auszunehmen — auf die Theorie hin, dass die Störer auf dem bedruckten
Rand sitzen — kostet weitere drei Pfeile. Die Sektordrähte laufen bis in die
Mitte, ihre Residuen erreichen die Scoring-Fläche also genauso leicht wie ein
Pfeil.

Vollständige Sweeps in
[erkennung-verbesserungen.md](erkennung-verbesserungen.md#2-gradientenabhängiger-schwellwert-verworfen).

### 5.12 Bettskalierter Schwellwert  *(verworfen)*

*Idee:* Der Schwellwert von 40 ist auf schwarzem Bett zu streng — dort kommen nur
38 % der Pfeil-Pixel darüber, gegen 90 % auf hellem. Also eine Schwellwert-Karte,
deren Enden pro Frame vom Board selbst abgelesen werden (schwarze Betten locker,
beige unverändert 40), interpoliert über die geglättete Referenz-Helligkeit.

*Warum verworfen:* Vier Varianten — roh, mit Seed-Hysterese, nur innerhalb der
Scoring-Fläche, nur für dunkler werdende Pixel — mit je drei Werten, **alle unter
der Baseline**, und in jeder fällt die Quote **monoton** mit der Lockerung. Es
gibt kein Optimum im Inneren. Die dunklen Pfeile gewinnen dabei genau das
Vorhergesagte (`pz` bis +6), die Wolfram-Boards verlieren mehr. Der Grund ist die
Fläche, nicht der Wert: eine über die ganze Suchfläche gelockerte Schwelle kauft
ein paar hundert echte Pfeil-Pixel gegen zehntausende Fremdpixel, und weil die
Fusion auf dem *breitesten* Fragment ankert, genügt eines davon, um den Fit zu
entführen. Vollständige Tabellen und die Konsequenz daraus in
[erkennung-blob.md](erkennung-blob.md).

### 5.13 Anker nach Überzeugungskraft statt nach Breite  *(verworfen)*

*Idee:* Die Fusion ankert auf dem **breitesten** Fragment und nennt es Flight.
Jedes breite, helle Fremdfragment konkurriert damit um den Anker, und der Anker
entscheidet den ganzen Fit. Also nicht das breiteste, sondern das
*überzeugendste* Fragment wählen — Fläche, Diff-Helligkeit, Kombinationen daraus.

*Warum verworfen:* Sechs Regeln über die vollen 285 Paare, Spanne **219 – 223**
gegen eine Baseline von 222. Breite, Fläche und Fläche × Helligkeit liefern
**identische** Ergebnisse, bis in die Aufschlüsselung pro Board — das breiteste
Fragment ist fast immer auch das größte, die Umsortierung wählt also dasselbe
Fragment. Die verbleibende Streuung ist Rauschen.

*Was der Fehlschlag zeigt:* Die Anker-Entführung ist real
(`pz_setup1/throw5/dart1`: der Fit ankert auf dem Registrierungs-Rest der
aufgedruckten Board-Zahlen und scort `MISS` bei r = 214 mm), aber der Störer ist
nach **jedem** Erscheinungsmerkmal überzeugender als der Pfeil: breit, hell,
flächig. Ihn trennt vom Pfeil nur, **wo** er liegt — im Surround, wo keine Spitze
stecken kann. Ein tragfähiger Anker-Test braucht also Board-Geometrie, keine
Pixelstatistik. Vollständige Tabelle in
[erkennung-blob.md §6.1](erkennung-blob.md#61-anker-entkoppeln-s-als-umsortierung-verworfen).

### 5.14 Anderer Differenz-Kanal: ΔV statt max|ΔBGR|  *(verworfen)*

*Idee:* Eine Vormessung mit Kontrolle auf leerem Board (Median über korrekt
gewertete Würfe, Band entlang der gefitteten Achse) verglich fünf Kandidaten für
den skalaren Differenzwert. **ΔV = `|max(B,G,R)_ref − max(B,G,R)_neu|` gewann
jedes einzelne Feld** im Signal-zu-Untergrund-Verhältnis:

| Pfeilteil | Bett | max\|ΔBGR\| | ΔV | ΔS | ΔE(Lab) | ΔC(ab) |
|---|---|---|---|---|---|---|
| Spitze | schwarz | 13.0× | **18.5×** | 4.0× | 8.9× | 4.3× |
| Spitze | creme | 19.8× | **37.0×** | 8.3× | 17.5× | 5.4× |
| Schaft | schwarz | 16.0× | **29.0×** | 2.9× | 9.4× | 4.5× |
| Schaft | creme | 15.0× | **20.5×** | 11.0× | 13.3× | 5.4× |
| Flight | schwarz | 40.5× | **79.0×** | 3.5× | 27.0× | 6.3× |
| Flight | creme | 24.2× | **31.0×** | 16.5× | 22.7× | 9.6× |

Der Grund ist der Untergrund: `max|ΔBGR|` maximiert über drei *unabhängig*
verrauschte Kanaldifferenzen und gibt dem Rauschen drei Chancen (Kontrolle 3–4),
ΔV bildet erst das Maximum und differenziert dann (Kontrolle 1–2).

*Warum trotzdem verworfen:* Über die vollen 285 Paare **schlechter auf jedem
Wert**, und monoton fallend mit der Lockerung:

| Kanal @ Schwelle | korrekt |
|---|---|
| max\|ΔBGR\| @ 40 (Baseline) | **227** |
| ΔV @ 40 | 218 |
| ΔV @ 30 | 217 |
| ΔV @ 25 | 196 |
| ΔV @ 20 | 155 |
| max(beide) @ 30 | 206 |
| max(beide) @ 25 | 173 |

*Zwei Lehren, beide übertragbar:*

1. **Das Verhältnis war die falsche Kennzahl.** ΔV verliert schon bei
   *gleichem* Schwellwert neun Pfeile — es ist keine Schwellwertfrage. Die
   Absolutwerte liegen in jeder Zeile niedriger, auf cremefarbenem Bett drastisch
   (Schaft 60 → 41, Flight 97 → 62). Bei einem festen Schnitt bei 40 zählt der
   Absolutwert, nicht das Verhältnis. Damit ist §5.5 nachträglich belegt: `V` ist
   eine helligkeitsartige Größe, und eine Farbänderung ohne Helligkeitsänderung
   fällt heraus.
2. **Es wurde das falsche Rauschen gemessen.** Die Argumentation „halber
   Untergrund, also halbe Schwelle gleich teuer" setzt voraus, dass die 40 durch
   Sensorrauschen gesetzt sind. Sie sind es nicht — sie sind durch
   **Registrierungs-Reste an Kanten** gesetzt (§5.11: mittlerer Gradient 52
   Grauwerte/Pixel bei den Pixeln über 40). Eine sub-pixelig verschobene Kante
   ändert `max(B,G,R)` genauso stark. ΔV senkt das Sensorrauschen und lässt die
   eigentliche Störquelle unberührt.

*Was gültig bleibt:* die Diagnose derselben Messung — **die Pfeilspitze liegt auf
schwarzem Bett im Median bei 39.0, bei einer Schwelle von 40**. Die Hälfte der
Spitzenpixel geht verloren, und die Spitze ist der einzige Teil, der fürs Scoring
zählt. Das Problem ist real; nur über den Kanal ist es nicht zu lösen.

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

Testdaten: fünf Boards (`cc`, `fh`, `pz`, `pz-light`, `tz`) über 16 Kamera-Setups,
je fünf bis zehn Wurfserien mit Basisbild + drei Pfeilen = **285 Detektions-Paare**,
verschiedene Winkel, Distanzen (0.63–1.69 px/mm) und Lichtverhältnisse. Jeder
Ordner trägt eine `ground_truth.txt` mit dem tatsächlichen Segment je Pfeil (gegen
die Videos korrigiert). Gemessen bei Client-Auflösung mit `run_all.py`.

Die Serien mit schwarzen Pfeilen (`pz`, `tz`) und die mit den späteren
Wolfram-Pfeilen (weiße Flights) liegen im selben Set. Die beiden sind
**gegenläufige** Fehlerfälle und heben sich in einer Gesamtzahl teilweise auf:
der schwarze Pfeil verschwindet über schwarzen Betten, der weiße Flight über den
beigen. Für eine Aussage über einen einzelnen Änderungsschritt ist deshalb die
Aufschlüsselung pro Board aussagekräftiger als der Gesamtwert.

### Genauigkeits-Verlauf

Jeder Entwicklungsschritt gegen **dasselbe** ursprüngliche 60-Paar-Set gemessen
(vier Setups eines Boards), damit der Beitrag jeder Änderung isoliert sichtbar
ist — ein A/B-Vergleich braucht eine feste Datenbasis:

| Schritt | Korrektes Segment |
|---|---|
| Größter Blob + zentrumsnächste Spitze (Baseline, §5.8/5.9) | 11 / 60 — **18.3 %** |
| + Flight-Orientierung der Spitze (§2.4) | 13 / 60 — **21.7 %** |
| + Fragment-Fusion (§2.3) | 29 / 60 — **48.3 %** |
| + Längen-Cap (§2.3) | **37 / 60 — 61.7 %** |

Die folgenden Schritte werden gegen das gewachsene 285-Paar-Set gemessen, und
zwar unter der Regel `NO_CHANGE` = `MISS` (§3) — auch rückwirkend, damit die
Zeilen vergleichbar bleiben:

| Schritt | Korrekt |
|---|---|
| Stand bei 285 Paaren | 216 / 285 — 75.8 % |
| + Warp-Gültigkeitsmaske (§2.2) | 218 / 285 — 76.5 % |
| (Gradienten-Seeds — gemessen, wieder entfernt, §5.11) | 221 / 285 — 77.5 % |
| (Bettskalierter Schwellwert — gemessen, verworfen, §5.12) | ≤ 217 / 285 |
| + Sättigungskanal auf hellen Betten (§2.2) | 222 / 285 — 77.9 % |
| (Anker-Umsortierung — sechs Regeln gemessen, verworfen, §5.13) | 219 – 223 / 285 |
| + Fusions-Reichweite 90 → 110 mm (§2.3) | 227 / 285 — 79.6 % |
| + `NO_CHANGE` als eigenes Truth-Label (§3) | **226 / 285 — 79.3 %** |

Die letzte Zeile ist **kein Rückschritt der Pipeline**, sondern eine Verschärfung
des Maßstabs: an der Erkennung hat sich nichts geändert, nur zählt ein
`NO_CHANGE` auf einem Bild mit sichtbarem Pfeil nicht mehr als Treffer (§3). Alle
Zeilen darüber sind unter der alten Konvention gemessen und untereinander
vergleichbar; wer sie mit der heutigen Zahl vergleicht, muss diesen einen Pfeil
mitrechnen.

Zwei Pfeile — weit weniger als erwartet. Die Maske entfernt ein Artefakt, das gar
keine Bildänderung ist, aber der Warp-Rand war nur *eine* Quelle breiter, heller
Fremdfragmente; die anderen bleiben. Der Versuch, auch die zu fassen, brachte
drei weitere Pfeile, kostete aber auf dem dunkelsten Board zwei und ist deshalb
nicht Teil der Pipeline (§5.11). Aufschlüsselung in
[erkennung-verbesserungen.md](erkennung-verbesserungen.md).

Die Fehler*verteilung* bewegt sich deutlicher als die Quote, und das ist die
interessantere Zahl:

| | ≤5 mm | 5–20 | 20–50 | >50 | Mittel | Max |
|---|---|---|---|---|---|---|
| Ausgangsstand | 33 | 12 | 6 | 18 | 35.2 | 227.4 |
| nach beiden Schritten | 29 | 12 | 9 | 13 | 28.1 | 166.6 |

Der strukturelle Schwanz schrumpft (>50 mm von 18 auf 13, Maximum von 227 auf
167 mm), ohne dass die Präzision leidet. Genau das war das Ziel: die Fälle, in
denen der Fit auf etwas anderem als dem Pfeil ankert.

**Ein Preis ist dabei belegt.** Pro Board: `tz` 54→56, `pz` 44→46, `pz-light`
74→75, `cc` 23→23, **`fh` 23→21**. `fh` und `cc` hatten vorher **null**
Mismatches über 20 mm (mittlere Abweichung 4.2 bzw. 3.4 mm) — dort gibt es kein
strukturelles Problem, das Gate kann also nur schaden. `fh` ist zugleich das
dunkelste Setup (Bett-Helligkeit 171–176 gegen 225 bei `pz-light`), das
Pfeil-Signal insgesamt schwächer, sodass eher eine Komponente unter den
Seed-Anteil rutscht. Als Bedingung formuliert: **das Gate hilft, wo das
Front-End-Signal stark genug ist, dass Kanten-Residuen die einzige
Verwechslungsgefahr sind** — bei schwachem Signal überwiegt der Verlust.

Nebenbei deckte der Schritt einen Zufallstreffer auf: ein Pfeil, der als `MISS`
korrekt gezählt wurde, weil die Pipeline den Randstreifen für einen Pfeil
außerhalb der Scoring-Fläche hielt. Ein gutes Beispiel dafür, warum eine reine
Label-Quote als einzige Metrik nicht reicht — ein Fehler kann sich als Treffer
tarnen, und nur die `off by`-Spalte und das Board-Modell im Bild (§4) zeigen das.

Seither ist das Test-Set auf **285 Paare** über fünf Boards und 16 Setups
gewachsen; die Pipeline erreicht darauf **226 / 285 — 79.3 %**, pro Board
73 – 87 %. Ein Blob wird praktisch immer gefunden (281/285 „lokalisiert"), und
die Ausnahmen sind Pfeile, die gar nicht steckenblieben (§3) — die
aussagekräftige Zahl ist die korrekte *Wertung*, nicht „irgendwo ein Pfeil".

### Was den Restfehler ausmacht

Die `off by`-Spalte (§4) trennt die 58 Mismatches in zwei Populationen, und die
sind unterschiedlich zu behandeln:

| Abstand zum erwarteten Segment | Anzahl | Charakter |
|---|---|---|
| ≤ 5 mm | 29 | Spitzen-Präzision, auf der falschen Seite eines Drahts |
| 5 – 20 mm | 12 | Achse leicht verdreht oder Spitze am Farbrand abgeschnitten |
| > 20 mm | 16 | strukturell: falsch verankerter Fit |
| nicht messbar | 1 | `IMPLAUSIBLE_SHAPE`, also keine gescorte Spitze |

Die **29 unter 5 mm** sind die Präzisionsgrenze — bei einem Draht von rund 1 mm
Breite und einer Spitzenlage auf wenige Millimeter genau ist das kein Fehler, den
ein besserer Algorithmus wegräumt. Die **16 über 20 mm** dagegen haben jeweils
eine benennbare Ursache und sind das eigentliche Ziel; sie werden in
[erkennung-verbesserungen.md](erkennung-verbesserungen.md) einzeln aufgeschlüsselt.

**Der strukturelle Teil ist der, der sich bewegt.** Über 20 mm waren es 23, jetzt
16 — die Fusions-Reichweite (§2.3) hat sieben Fälle geräumt, in denen der Fit auf
einem Teilstück des Pfeils saß. Die Präzisionsklasse darunter bleibt praktisch
unverändert (32 → 29), wie es sein soll: an ihr wurde nichts geändert. Sichtbar
ist derselbe Effekt in der Kohäsions-Tabelle (§4) — die mittlere Abweichung der
einkomponentigen Blobs fällt von 4.8 mm auf **2.4 mm**, weil die Achse jetzt auf
der ganzen Pfeillänge sitzt statt auf einem abgeschnittenen Stück.

Zwei wiederkehrende Muster stechen heraus:

- **Breite, helle Fremdfragmente gewinnen die Flight-Wahl.** Die Fusion ankert
  auf dem breitesten Fragment; alles Breite und Helle, das kein Pfeil ist,
  entführt damit den ganzen Fit. Der Warp-Rand war davon der krasseste Fall und
  ist behoben (§2.2), aber nicht der einzige: der Sub-Pixel-Rest der
  Registrierung lässt die weißen Board-Zahlen im Surround aufleuchten, und die
  sind ebenfalls breit und hell. Das erklärt die verbliebenen 14 Fälle über
  50 mm. Der naheliegende Gegenzug — den Anker nach anderen Merkmalen wählen —
  ist gemessen und **trägt nicht** (§5.13): der Störer ist nach jedem
  Erscheinungsmerkmal überzeugender als der Pfeil. Was ihn trennt, ist seine
  **Lage** auf dem Board, nicht sein Aussehen.
- **Farb-gegatetes Signal, in beide Richtungen.** Der schwarze Pfeil difft nur
  über hellen Segmenten und ist über schwarzen ≈ unsichtbar (§5.10). Bei den
  neuen Pfeilen mit weißen Flights ist es gespiegelt: über einem beigen Bett
  liegt die größte BGR-Kanaldifferenz bei etwa 14, unter dem Schwellwert von 40.
  In der **Sättigung** sind es rund 29 — dieser Kanal wird seit §2.2 mit
  ausgewertet und war vier Pfeile wert. Die gespiegelte Hälfte, der dunkle Pfeil
  auf schwarzem Bett, ist damit **nicht** gelöst: dort ist S numerisch
  unbrauchbar, und ein gelockerter Schwellwert ist es auch (§5.12).

Die Laufzeit pro Detektion ist noch nicht systematisch gemessen.

### Ein Confound im Testset: die doppelte JPEG-Generation

`as_client_would_send` (`scripts/common.py`) bildet die Client-Kette nach, damit
der Offline-Lauf den Detektor mit demselben Material füttert wie der Betrieb:
auf 1280 px verkleinern, einmal JPEG q85. Das Verkleinern war bedingt, das
Encodieren nicht — ein Foto, das schon innerhalb der Aufnahmegröße lag, bekam
also eine **zweite** Kompressionsgeneration, die es live nie sieht.

Betroffen waren nicht verstreute Einzelbilder, sondern **80 von 380
Eingabefotos, und zwar genau `cc_setup1/2` und `fh_setup1/2`** — zwei ganze
Boards von fünf. Auf den live aufgezeichneten Serien
([auswertung.md](auswertung.md)) kostete derselbe Effekt 81.8 % → 54.5 %.

Der Fix ist eine Bedingung: ein Bild innerhalb der Aufnahmegröße wird
unverändert durchgereicht. Gemessen über die vollen 285 Paare, vorher/nachher:

| | vorher | nachher |
|---|---|---|
| Korrekt | 227 / 285 | **227 / 285** |
| `cc` | 22 / 30 | **24 / 30** |
| `fh` | 23 / 30 | **21 / 30** |
| `pz`, `pz-light`, `tz` | 46 / 78 / 58 | unverändert |
| Mittlere Abweichung der Mismatches | 32.8 mm | 34.8 mm |

**Die Gesamtquote bewegt sich nicht.** Die drei unbetroffenen Boards sind
bitgleich — die erwartete Kontrolle, denn ihre Fotos liegen alle über 1280 px
und laufen durch denselben Code wie zuvor. Bei den beiden betroffenen heben sich
die Änderungen auf: `cc` gewinnt fünf Würfe, die vorher grob danebenlagen
(S7 statt S16, S15 statt Bull), `fh` und `cc` verlieren zusammen fünf, von denen
vier nur um 0.9 – 1.0 mm auf der falschen Drahtseite liegen.

Ein Fall kippt strukturell: `fh_setup1/throw5/dart3` geht von `S5` (6.8 mm
daneben, 2 Fragmente) auf `MISS` (126.6 mm, **3** Fragmente). Ohne die zweite
Kompression kommt der Pfeil zerstückelter an — plausibel, weil q85 tiefpassfiltert
und `fh` das dunkelste Setup mit dem schwächsten Signal ist (§6). Die beiden
Pfeile dieser Serie tragen allerdings unsichere Truth-Labels (`D5?`, `S20?`), der
Einzelfall trägt also wenig.

**Was das Ergebnis wert ist:** nicht eine bessere Quote, sondern eine ehrlichere.
Die 79.6 % maßen vorher zu einem Fünftel Pipeline *plus Artefakt*; sie messen
jetzt nur die Pipeline — und kommen auf denselben Wert. Damit ist die Zahl
gegen diesen Confound nachweislich robust, statt es nur zu sein.

### Messung im laufenden Spiel

Neben dem festen Testset misst sich die Pipeline seit neuestem auch beim
normalen Spielen: was die Kamera bucht, wird gegen das gehalten, was die Spieler
am Ende übernehmen. Weil eine verpasste Erkennung mehrere Korrekturen kostet,
werden die beiden Sequenzen je Visit *ausgerichtet* statt Korrekturen gezählt —
Verfahren, Kennzahlen und Grenzen in [auswertung.md](auswertung.md). Korrigierte
Runden legen ihre Kamerabilder als Wurfserie ab und wachsen damit ins Testset
hinein.

---

## 7. Offene Punkte

Die konkret geplanten Schritte mit Befund, Fix und erwartetem Hebel stehen in
[erkennung-verbesserungen.md](erkennung-verbesserungen.md). Hier bleiben die
längerfristigen Punkte:

- **Signal statt Algorithmus — teilweise beantwortet.** Die These war, das
  Front-End sei die stärkste Stellschraube: schwarze Pfeile ein pathologischer
  Fall (§5.10). Inzwischen gibt es Serien mit Wolfram-Spitzen und weißen Flights
  (`cc`, `fh`, `pz-light`) zum Vergleich. Ergebnis: die Spitzenerkennung wird
  deutlich besser, aber der weiße Flight erzeugt über beigen Betten sein eigenes
  Loch (§6). „Helleres Pfeilmaterial" allein ist also keine Lösung, sondern
  verschiebt nur, *welche* Betten blind sind — das Front-End braucht einen
  Kanal, der beide Fälle trägt. Als „Bedingungen, unter denen die Methode trägt"
  ist das ein eigenständiges Ergebnis für die Arbeit.
- **Fragment-Ankerung, jetzt eingegrenzt.** Eine Umsortierung des Ankers nach
  Breite, Fläche und Helligkeit ist über sechs Regeln gemessen und bringt nichts
  (§5.13) — die drei stärksten liefern sogar identische Ergebnisse, weil sie
  dasselbe Fragment wählen. Offen bleibt damit genau die eine Variante, die noch
  nicht probiert ist: ein Anker-Test über die **Board-Geometrie** (Radius des
  Fragment-Schwerpunkts durch die Homographie), der den Surround ausschließt, wo
  keine Spitze stecken kann. Alternativ das kantenbasierte Front-End
  (strukturelle statt Intensitäts-Differenz), um mehr Schaft-Signal zu gewinnen.
- **3D-lite Extrapolation.** Mit Kamera-Intrinsics (einmalige Vorkalibrierung)
  liefert die Homographie die volle Pose (`H = K·[r₁ r₂ t]`); eine bekannte
  Pfeillänge auf der Bild-Geraden ließe sich dann exakt mit der Board-Ebene
  schneiden. Bricht die Kalibrierung nicht, baut auf ihr auf — Ausblick.
- **Gelernter Tip-Detektor.** Robustester Endzustand gegen schwarz-auf-schwarz;
  die Ground-Truth-Infrastruktur (§6) ist der erste Schritt zu Trainingsdaten.
- **Board-Clear bei Auto-Weiterschaltung.** Das Re-Base am Rundenwechsel (§1)
  hängt daran, dass der Wechsel bestätigt wird, also nach dem Ziehen kommt. Ohne
  Bestätigung feuert er direkt nach dem dritten Dart. Siehe
  [client-diff-verbesserungen.md §3](client-diff-verbesserungen.md#3-auto-advance-vom-kameramodus-entkoppeln).
- **Größen-Ablehnung nur grob.** `IMPLAUSIBLE_SHAPE` fängt seit
  [client-diff-verbesserungen.md §1](client-diff-verbesserungen.md#1-plausibilitätsgrenze-auf-dem-blob-server)
  ab, was klar zu groß ist (>250 mm lang oder >8000 mm²). Die Grenzen liegen weit
  oben, weil ein echter Pfeil im Testsatz bis 177 mm lang wird — der Bereich
  dazwischen ist ungeprüft und braucht ein anderes Merkmal als die reine Größe.
- **Verdeckung.** Aktuell nur implizit gelöst (neuer Pfeil verdeckt alten →
  Problem; drei nebeneinander → kein Problem). Das Linien-Modell hilft bei
  Teilverdeckung mehr als ein Schwerpunkt-Ansatz, der explizite Umgang ist aber
  Phase-3-Thema.
- **Objektivverzeichnung** wird von der Homographie geerbt — derselbe
  Randfehler wie bei der Kalibrierung.
