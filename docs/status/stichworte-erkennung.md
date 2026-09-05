# Stichwortzettel – Pfeil-Erkennung

Stand: 24.08. · Kalibrierung war letztes Gespräch, hier geht es nur um die Detektion.

---

## 0. Was sich seit dem letzten Mal geändert hat

- **Testset ist gewachsen:** 285 Detektions-Paare, **5 Boards** (`cc`, `fh`, `pz`, `pz-light`, `tz`), **16 Kamera-Setups**, 0.63–1.69 px/mm, verschiedene Lichtverhältnisse.
- Jeder Ordner hat eine **`ground_truth.txt`** (gegen die Videos beschriftet) → echte Segment-Accuracy, nicht mehr Sichtprüfung.
- Zwei **gegenläufige Pfeil-Typen** im Set: alte dunkle Pfeile (`pz`, `tz`) und neue Wolfram-Pfeile mit weißen Flights (`cc`, `fh`, `pz-light`). Wichtig fürs Argumentieren — sie heben sich in einer Gesamtzahl teilweise auf, deshalb immer Aufschlüsselung pro Board.
- **Stand: 227 / 285 = 79.6 %** korrekte Wertung, pro Board 73–87 %. Baseline war 18.3 %.

---

## 1. Grundprinzip

**Pfeil nicht am Aussehen erkennen, sondern die Änderung erkennen.**
- Pfeil an sich ist ein schlechtes Ziel: dunkel + dünn, auf einem Board das dunkel und voller dünner Drähte ist.
- Stattdessen: **Frame-Differenz** — was hat der Wurf hinzugefügt.
- Differenz gegen den **vorherigen Frame**, nicht gegen das leere Board → steckende Pfeile heben sich auf. **Rollender Referenz-Frame.**
- Verdeckung wird erst zum Problem, wenn ein *neuer* Pfeil einen alten verdeckt — nicht schon, wenn drei nebeneinander stecken.

---

## 2. Pipeline (5 Schritte)

1. **Registrierung** (ORB, board-maskiert) — neuen Frame auf die Referenz warpen.
   - Handkamera driftet: 25 px Versatz = **~117 000** aufleuchtende Pixel, Pfeil selbst = ein paar hundert.
   - Maske aufs Board, weil **Board und Wand in verschiedenen Tiefen** liegen → sonst rastet die Homographie auf der (größeren) Wand ein und lässt das Board schief. Die Maskierung ist so wichtig wie die Registrierung selbst.
   - Steckende Pfeile sind Ausreißer, aber ein paar gegen 340–1200 Inlier → RANSAC verwirft sie mühelos.
2. **Differenz + Schwellwert + Cleanup**
   - **Pro Farbkanal differenzieren, dann max** — nicht erst zu Grau. Barrel vor schwarzem Segment ist in der *Helligkeit* fast identisch, in der *Farbe* nicht.
   - Zweiter Kanal: **Sättigung, aber nur auf hellen Betten** (weißer Flight auf beigem Bett: 14 Grauwerte in BGR, 29 in S). Gate kommt aus dem Board selbst (Homographie liefert die Bett-Mittelpunkte).
   - Schwelle 40 (Sensorrauschen 2–4). Erst Speckle-Flächengrenze, **dann** schließen — umgekehrt würde das Schließen Rauschen zu überlebensfähigen Blobs verbinden.
3. **Fragment-Fusion** — der Pfeil kommt in Bruchstücken an. Fragmente auf einer Geraden zusammenfügen, **Anker = breitestes Fragment = Flight** (Federn spreizen die Silhouette). Hypothese-und-zähle wie bei der Kalibrierungs-RANSAC, aber deterministisch, weil am Flight verankert. **Längen-Cap 110 mm.**
4. **Hauptachse (PCA) + Spitze** — Spitze = Ende **gegenüber dem Flight**, also formbasiert. Über 4 mm gemittelt, aber **nur quer zur Achse** (längs mitteln würde den Pfeil verkürzen).
5. **Scoring** — Spitze durch Homographie → mm → Segment (reine Geometrie).

> **Alle Größen in Board-Millimetern definiert**, pro Frame über die Homographie in Pixel umgerechnet → derselbe Parametersatz gilt bei jeder Kameradistanz.

---

## 3. Genauigkeits-Verlauf

**Erste vier Schritte** (gegen dasselbe 60-Paar-Set, damit jeder Beitrag isoliert sichtbar ist):

| Schritt | korrekt |
|---|---|
| Größter Blob + zentrumsnächste Spitze (Baseline) | **18.3 %** |
| + Flight-Orientierung der Spitze | 21.7 % |
| + Fragment-Fusion | 48.3 % |
| + Längen-Cap | **61.7 %** |

**Danach gegen die vollen 285 Paare:**

| Schritt | korrekt |
|---|---|
| Stand bei 285 Paaren | 216 — 75.8 % |
| + Warp-Gültigkeitsmaske | 218 — 76.5 % |
| + Sättigungskanal auf hellen Betten | 222 — 77.9 % |
| + Fusions-Reichweite 90 → 110 mm | **227 — 79.6 %** |

Dazwischen liegen **drei komplett verworfene Anläufe** (siehe §5).

**Fehlerverteilung ist die interessantere Zahl als die Quote:**

| | ≤5 mm | 5–20 | 20–50 | >50 | Mittel | Max |
|---|---|---|---|---|---|---|
| Ausgangsstand | 33 | 12 | 6 | 18 | 35.2 mm | 227 mm |
| jetzt | 29 | 12 | 9 | 13 | 28.1 mm | 167 mm |

→ Der **strukturelle Schwanz** schrumpft, die Präzisionsklasse bleibt gleich. Genau so soll es sein.

**Restfehler zerfällt in zwei Populationen:**
- **29 unter 5 mm** — Draht ist ~1 mm breit, das ist die Präzisionsgrenze. Kein Algorithmus räumt die weg.
- **16 über 20 mm** — strukturell, falsch verankerter Fit. Das eigentliche Ziel.

---

## 4. Fragen zur Technik — hier brauche ich Input

### 4a. Die eine Frage, die ich stellen will

**Situation:** Der Restfehler zerfällt sauber in zwei Hälften. Die Präzisionshälfte (≤5 mm) akzeptiere ich als Grenze. Die strukturelle Hälfte hat *eine* gemeinsame Ursache — der Pfeil kommt nicht als ein Objekt an, sondern als Streu-Fragmente, und die Fusion ankert dann auf dem falschen Fragment.

**Was ich schon durch habe:** vier Anläufe am Front-End (Schwelle global / gradientenabhängig / bettskaliert / anderer Kanal) und einer an der Anker-Regel — alle gemessen, alle verworfen (§5c).

**Richtungen, die ich sehe** — dazu hätte ich gern eine Einschätzung, welche davon in Aufwand und Anspruch am besten passt:

1. **Korridor-Wachstum, zwei Pässe.** Pass 1 streng → Achsen-Hypothese; Pass 2 lockert nur im 8-mm-Band entlang der Achse. Macht die Lockerung bezahlbar, die global gescheitert ist. *Mein Favorit — folgt direkt aus der Messung.*
2. **Strukturdifferenz statt Intensitätsdifferenz** (lokale Varianz / Gradientenbetrag / NCC). Für schwarz-auf-schwarz die eigentlich passende Größe: der Pfeil verdeckt die Sisal-Textur, auch wenn er den Mittelwert nicht ändert.
3. **Anker-Test über Board-Geometrie** statt Pixelstatistik — Fragment-Schwerpunkt durch die Homographie, Surround ausschließen. *Der Störer in §4d sitzt bei r = 193–222 mm, also komplett außerhalb der Scoring-Fläche — dieser eine Test hätte ihn erledigt.* Dazu: die Reichweite vom Board aus statt vom Anker aus denken.
4. **Gelernter Tip-Detektor** — Ground-Truth-Infrastruktur steht, aber anderer Arbeitstyp.

**Die offene Frage:** Gibt es aus seiner Sicht einen etablierten Ansatz für genau dieses Problem — *dünnes, kontrastarmes, starres Objekt vor strukturiertem Hintergrund, das die Segmentierung zerreißt* — den ich übersehe? Ich bin die ganze Zeit in „Schwellwert + Zusammensetzen" unterwegs; falls es dafür eine Standardformulierung gibt (Liniensegment-Detektion, Ridge/Tubularity-Filter, MRF/Graph-Cut mit Geradheits-Prior, Template-Matching über die bekannte Pfeilform), wäre das der Punkt, an dem Literatur mehr bringt als der nächste eigene Versuch.

### 4b. Fehlerfälle zum Vorzeigen — Bilder liegen bereit

Sechs Serien durch `run_debug.py`, je 9 Stufenbilder pro Pfeil, unter
`backend/testdata/detection/_results_debug/<setup>/<serie>/dartN/`.
Die aussagekräftigste Ansicht ist fast immer **`07_components.jpg`** (welche Fragmente wurden zusammengefügt, entlang welcher Geraden) gegen **`03_difference.jpg`** (war der Pfeil überhaupt in der Differenz).

**Klasse A — Anker-Entführung** *(der Fit sitzt auf etwas, das kein Pfeil ist)*. Ansicht: `07_components.jpg`. Grau = verworfen bzw. außer Reichweite, grün = gefuster Pfeil, orange = Anker.

| Fall | Was man sieht | Zahlen |
|---|---|---|
| `pz-light_setup3/throw7/dart1` | **Der Fall zum Vorführen** (ausgezählt, §4d). Anker im Surround links oben; der echte Pfeil liegt dunkelgrau nahe Bull — außer Reichweite, also nie betrachtet | **78 Komponenten**, 18 in Reichweite, 3 gefused · `MISS` bei r = 216 mm statt `S7` — **220 mm daneben** |
| `tz_setup5/throw1/dart1` | Dieselbe Klasse, anderer Störer: Anker auf einem **hellen Fleck am oberen Board-Rand**, die Achse läuft von dort quer nach unten. Echter Pfeil wieder grau bei 10 Uhr | Blob **118 × 47 mm** · `D4` statt `S14` — 179 mm daneben |
| `pz_setup1/throw5/dart1` | Dieselbe Klasse bei grober Auflösung (0.67 px/mm) | 50 Komponenten · Blob **197 × 20 mm**, länger als jeder echte Pfeil (max. 177 mm) · `MISS` bei r = 221 mm |

**Klasse B — Orientierung kippt** *(Pfeil korrekt gefunden, falsches Ende gescort)*. Ansicht: **`08_axis.jpg`** — Kreuz = gescorte Spitze, Kreis = angenommener Flight, beide Endbreiten stehen im Bild.

| Fall | Was man sieht | Zahlen |
|---|---|---|
| `tz_setup5/throw4/dart2` | Der Blob liegt sauber auf dem Pfeil, aber Kreuz und Kreis sind **vertauscht**: gescort wird das Schaft-/Flight-Ende, das perspektivisch weit über den Board-Rand hinausragt | Endbreiten 28.5 gegen 23.6 px, **Margin nur 5.3 px** · Spitze bei r = **316 mm** → `MISS` |
| `tz_setup5/throw4/dart3` | Identisches Muster im selben Setup | 4.4 gegen 10.8 px, **Margin 6.4 px** · r = **315 mm** → `MISS` |

**Klasse C — Kontrastfälle** *(zum Zeigen, dass es auch funktioniert bzw. sauber abgelehnt wird)*.

| Fall | Was man sieht | Zahlen |
|---|---|---|
| `pz-light_setup2/throw5/dart1` | Einziger `IMPLAUSIBLE_SHAPE` im Set — die Maske ist praktisch das halbe Bild, die Größen-Ablehnung greift | **113 Komponenten**, Blob **363 × 110 mm** |
| `pz_setup3/throw1/dart2` | Der saubere **Präzisionsfall**: ein Blob, nichts falsch verankert, nur zu kurz für eine stabile Achse | 1 Komponente, Blob nur **37 × 13 mm** → `T20` statt `S20`, 1.5 mm daneben |
| `tz_setup5/throw4/dart1` | Direkt daneben derselbe Wurf, der funktioniert: schlanker durchgehender Blob | Blob **104 × 8 mm** → `S13`, korrekt |

### 4c. Zwei Befunde aus diesem Debug-Lauf, die noch nirgends stehen

1. **Klasse B ist eine eigene Fehlerursache, die ich bisher nicht als solche geführt habe.** Die Doku behandelt die Spitzen-Orientierung als *gelöst* (§5b: „zentrumsnächstes Ende" → „Ende gegenüber dem breiteren"). Der Breiten-Test setzt aber voraus, dass **der Flight überhaupt in der Maske ist** — und genau das ist bei dunklem Flight auf dunklem Board nicht der Fall. Dann ist das breiteste Ende der Barrel, also die Spitze, und der Pfeil wird von hinten aufgezäumt. Der Formfehler und der Signalfehler sind hier gekoppelt.
2. **Die Endbreiten-Margin ist ein fertiges Konfidenzmaß, das ungenutzt herumliegt.** Beide gekippten Fälle haben eine Margin von **5.3 bzw. 6.4 px** — die Entscheidung war ein Münzwurf, und das steht bereits im Trace. Eine knappe Margin als „unsicher" zu melden statt still zu scoren wäre billig zu bauen und passt zum geplanten Ambiguitäts-Guard.

**Beim Erzählen sauber trennen:** das sind 6 Serien / 18 Pfeile, kein Sweep über die 285 Paare. Klasse A ist über den ganzen Satz belegt (die >20 mm-Fälle), Klasse B ist an zwei Pfeilen beobachtet — als Hypothese formulieren, die noch zu messen ist.

### 4d. `pz-light_setup3/throw7/dart1` ausgezählt — die Kettenreaktion

Der Fall, an dem sich das Problem in einer Minute erklären lässt. Bilder: `03_difference.jpg` neben `07_components.jpg` legen.

**Farblegende `07_components.jpg`:** dunkelgrau = außer Reichweite des Ankers · hellgrau = in Reichweite, aber nicht auf der Geraden · grün = gefuster Pfeil · orange = Anker · cyan = die gefittete Gerade.

**Schritt 1 — die Ankerwahl kennt die Fläche nicht.** Der Anker ist das **breiteste** Kandidaten-Fragment, Helligkeit nur als Gleichstand-Brecher; die Fläche steht nicht im Sortierschlüssel.

| | Fläche | Breite | Diff-Helligkeit | Radius |
|---|---|---|---|---|
| Label 40 — der echte Flight | **2223 px** | 12.1 mm | **156** | 33 – 95 mm |
| Label 27 — der gewählte Anker | 1529 px | **14.1 mm** | 48 | **193 – 222 mm** |

Der Störer gewinnt um **2.0 mm Breite**, bei 45 % weniger Fläche und einem Drittel der Helligkeit — und er sitzt vollständig im Surround, wo per Definition keine Spitze stecken kann.

**Schritt 2 — die Reichweite wird vom Anker aus gemessen, nicht vom Board aus.** `_MAX_DART_LENGTH_MM = 110 mm`; der echte Flight liegt **155 mm** vom Anker entfernt, der Schaft **182 mm**. Beide fallen raus, *bevor* die Richtungsabstimmung beginnt. Sie sind dunkelgrau, also nicht „abgelehnt", sondern **nie betrachtet**: 18 der 78 Komponenten waren in Reichweite, der Pfeil in keiner davon.

**Eine falsche Entscheidung, vier Folgen:** Anker falsch → Reichweite falsch zentriert → Pfeil ausgeschlossen → Achse auf dem Störer → `MISS` bei r = 216 mm.

**Es ist kein Signalproblem.** In `03_difference.jpg` ist der Pfeil das **hellste Objekt im ganzen Bild** — Flight leuchtend, Schaft als dünne Spur zum Bull. Die Information war da und wurde verworfen. Das ist das beste Einzelargument dafür, dass der Hebel im Modell liegt und nicht im Front-End.

**Gegenprobe (gemacht):** Ankerregel testweise auf *Fläche* umgestellt, sonst nichts geändert → derselbe Fall scort **`S7`**, exakt die Ground Truth.

> **Achtung, hier ist meine eigene Doku überholt.** [erkennung-blob.md §6.1](../feature/erkennung-blob.md) sagt, Breite und Fläche wählen „fast immer dasselbe Fragment" und liefern identische Quoten (222). Dieser Fall zeigt, dass das nicht durchgängig stimmt — und jener Sweep lief bei **90 mm** Reichweite, also vor der Umstellung auf 110 mm. Anker-Regel und Reichweite greifen ineinander, das Ergebnis ist damit nicht mehr aktuell. **Der Sweep gehört mit 110 mm wiederholt**, bevor ich „Anker-Umsortierung bringt nichts" weiter als Ergebnis vertrete.

---

## 5. Verworfene Ansätze — der Hauptteil

### 5a. Grundsätzliche Richtungsentscheidungen

| Ansatz | Warum verworfen |
|---|---|
| **Erscheinungsbasiert** (Hough-Linien / Kontur, so stand es im Konzept-Draft) | Pfeil = dunkel + dünn auf Board voller dunkler dünner Drähte. Hough-Linien fänden ebenso die Sektordrähte. → **grundlegender Richtungswechsel** ggü. dem Draft |
| **Differenz gegen leeres Board** | Dann leuchten *alle* steckenden Pfeile auf, bereits gezählte werden erneut detektiert |
| **Zwei unabhängige Ellipsen-Fits statt Registrierung** | Zwei Fits aufeinanderfolgender Frames drifteten um **7 %** in den Achsen — genug, dass jeder Draht des Boards aufleuchtet |
| **Unmaskierte Registrierung** | Fit rastet auf der Wand ein (andere Tiefe), Board bleibt schief |
| **Grauwert-Differenz statt Farbkanäle** | Farbänderung ohne Helligkeitsänderung fällt heraus. War lange nur *plausibel* — inzwischen über die ΔV-Messung (4c) nachträglich belegt |

### 5b. Einzelne Bausteine

| Ansatz | Warum verworfen |
|---|---|
| **Morphologisches Opening gegen Speckle** | Kleinstes OpenCV-Element ist 3×3 = bei 0.6–0.9 px/mm **3–5 mm, breiter als der Pfeil**. Warf 60 % der Pfeil-Pixel weg → stattdessen simple Flächengrenze, erodiert nichts |
| **Einzelner Extrempixel als Spitze** | Instabil — das ist, was der Schwellwert zufällig gefasst hat |
| **Größter Blob als Pfeil** | Der schwarze Pfeil kommt fragmentiert an; größter Blob = das Stück über der hellsten Fläche, meist nahe der Mitte. **Das war die 18.3 %-Baseline** |
| **Zentrumsnächstes Ende als Spitze** | Gilt nur solange der Flight nach außen zeigt. Pfeil hoch am Board → Flight lehnt perspektivisch über die Mitte zurück → wird von seinem Flight aus gescort, fälschlich `MISS`. Genau die steilen Fälle, für die das System gebaut ist |
| **Anker nach „Überzeugungskraft" statt Breite** ⚠️ | 6 Regeln (Fläche, Helligkeit, Kombinationen) über 285 Paare, Spanne **219–223** gegen Baseline 222 — schien zu zeigen, dass das breiteste Fragment fast immer das größte ist. **Gemessen bei 90 mm Reichweite, also überholt** — Gegenbeispiel und Begründung in §4d |
| **Scoring-Flächen-Ausnahme beim Kanten-Gate** | Theorie: Störer sitzen auf dem bedruckten Rand. Falsch — Sektordrähte laufen bis in die Mitte, ihre Residuen erreichen die Scoring-Fläche genauso leicht. Kostete 3 Pfeile |

### 5c. Vier Anläufe auf dasselbe: das Front-End · **alle vier gescheitert**

Alle vier setzen an der **pro-Pixel-Entscheidung über die gesamte Suchfläche** an.

| Anlauf | Idee | Ergebnis |
|---|---|---|
| Schwelle **global senken** | schwarz-auf-schwarz sichtbar machen | 40 und 20 identisch, bei 12 Absturz |
| Schwelle an den **Gradienten** koppeln | Registrierungs-Reste an Kanten wegdrücken | +3 gesamt, aber **−2 auf dem dunkelsten Board** → entfernt |
| Schwelle ans **Bett** koppeln | Schwelle pro Bettfarbe selbstkalibrieren | 4 Varianten × 3 Werte, **alle unter Baseline**, alle monoton fallend |
| **anderen Kanal** wählen (ΔV) | besseres Signal-zu-Rausch | schlechter auf **jedem** Wert |

**Der vierte ist der lehrreichste**, weil die Vormessung dafür sprach: ΔV gewann im Signal-zu-Untergrund-Verhältnis **jedes einzelne Feld** der Tabelle (bis 79× gegen 40×) und verlor trotzdem 9 Pfeile.

**Die drei übertragbaren Lehren:**
1. **Das Verhältnis ist nicht die Entscheidungsgröße, solange die Schwelle fest ist.** Der Schnitt bei 40 fragt nach dem *Absolutwert*, und den verliert ΔV (Flight auf creme: 97 → 62).
2. **Man muss das richtige Rauschen messen.** Die 40 sind *nicht* durch Sensorrauschen gesetzt (das liegt bei 2–4), sondern durch **Registrierungs-Reste an Kanten** — die Pixel über 40 haben im Mittel einen Gradienten von 52 Grauwerten/Pixel. ΔV senkt das Sensorrauschen und lässt die eigentliche Störquelle unberührt.
3. **Ohne Kontrollmessung wäre die falsche Entscheidung gefallen.** ΔS sah auf schwarzem Bett großartig aus (63.3 gegen 31.2 bei BGR) — bis die Kontrolle auf *leerem* Bett schon 26.9 ergab. `S = (max−min)/max`, und wo `max` klein ist, bläst Rauschen die Sättigung auf → Verhältnis nur 2.4×, der schlechteste aller Kanäle.

**Diagnose-Kriterium, das dabei entstanden ist:**
> **Optimum bei „Änderung aus" = Strukturproblem. Optimum im Inneren = Parameterproblem.**

Bei allen vier Front-End-Anläufen lag das Optimum exakt bei „aus" → kein Tuning-Problem. Beim Längen-Cap dagegen (90/110/130/150/180 mm) gab es ein echtes Maximum bei 110 → der Wert war schlicht falsch gewählt. **Der einzige Anlauf mit innerem Optimum war auch der einzige, der etwas gebracht hat.**

---

## 6. Was der gemeinsame Nenner ist (die aktuelle These)

- Die Suchfläche hat bei 1 px/mm rund **300 000 Pixel**. Ein Pfeil hat ein paar hundert.
- Eine global gelockerte Schwelle kauft ein paar hundert echte Pfeil-Pixel gegen **zehntausende** Fremdpixel.
- Und weil der Anker „breitestes Fragment" heißt, genügt **ein** breites Fremdfragment, um den ganzen Fit zu entführen.
  - Belegt: `pz-light_setup2/throw8/dart1` → **144 Komponenten**, Anker sitzt auf dem BLADE‖6-Schriftzug am Surround, Pfeil steckt auf 10 Uhr, Ergebnis `MISS` bei r = 196 mm.

> **Die Schwelle war nie das Problem — die Reihenfolge war es.**
> Erst schwellen, dann ein Objekt suchen, heißt **jede Lockerung global bezahlen**.
> Erst ein Objekt hypothetisieren, dann in seinem Korridor lockern, heißt sie fast umsonst bekommen.

Dieselbe Hypothetisieren-und-zählen-Logik, die bei der Kalibrierung den Board-RANSAC trägt.

**Das Ziel, an dem sich alles messen lassen muss — und es ist jetzt direkt messbar:**
> Eine Detektion = **eine** zusammenhängende Komponente.

| Fragmente | Quote | mittl. Abweichung |
|---|---|---|
| 1 (ein Blob) | 81 % | 2.4 mm |
| 2 | 79 % | 6.3 mm |
| 3–4 | 69 % | 17.5 mm |
| 5+ | 50 % | 13.6 mm |

**Nur 96 von 280 Pfeilen (34 %) kommen als ein Stück an.** Vorher war das eine Plausibilitätsannahme, jetzt eine Zahl.

**Was der Mensch benutzt und die Pipeline nicht:** Geradheit (wird heute erst *nach* dem Schwellwert benutzt, also nachdem die Information weg ist), Silhouetten-Kante, Textur, Glanz, Schatten, Anzahl.

**Nächster Schritt:** Korridor-Wachstum, zwei Pässe. Pass 1 streng → Achsen-Hypothese. Pass 2 lockert nur in einem 8-mm-Band entlang dieser Achse. Dort ist die Fläche **drei Größenordnungen kleiner** — dieselbe Schwelle von 16, die global scheiterte, hätte dort fast nichts anzuziehen.

---

## 7. Methodisch — was ich davon in die Arbeit nehme

- **Negativergebnisse als Bedingungen formulieren, nicht als Misserfolge.** Beispiel: „Kanten-Gating hilft nur dort, wo das Front-End-Signal stark genug ist, dass Kanten-Residuen die einzige Verwechslungsgefahr sind." Das ist eine übertragbare Aussage, kein gescheiterter Versuch.
- **A/B-Disziplin:** feste Datenbasis, jeder Schritt einzeln gemessen, ohne Vorher/Nachher-Zahl gilt nichts als erledigt. Auch die Metrik-Änderung (`NO_CHANGE` = `MISS`, beides null Punkte) wurde **rückwirkend** angewandt, damit die Zeilen vergleichbar bleiben.
- **Kontrollmessung ist Pflicht**, sonst misst man Rauschen und nennt es Signal.
- **Ein Fehler kann sich als Treffer tarnen:** ein Pfeil galt als korrekter `MISS`, weil die Pipeline den Warp-Randstreifen für einen Pfeil außerhalb der Scoring-Fläche hielt. Nur die `off by`-Spalte und das eingezeichnete Board-Modell zeigen das — reine Label-Quote reicht als Metrik nicht.
- **Debug-Infrastruktur als Methode:** 9 Bilder pro Detektion, jedes beantwortet genau eine Frage. Der Längen-Cap-Fehler (der größte Einzelhebel seit langem) ist an einer Konsolen-Zeile aufgefallen, nicht an der Accuracy.

---

## 8. Offene Punkte

- **Signal statt Algorithmus — teilweise beantwortet.** These war: helleres Pfeilmaterial löst das. Ergebnis: es **verschiebt nur, welche Betten blind sind** (schwarzer Pfeil verschwindet über schwarzem Bett, weißer Flight über beigem). Symmetrisches Problem, beide Fälle im selben Testset.
- **Anker-Test über Board-Geometrie** statt Pixelstatistik — der Störer ist nach *jedem* Erscheinungsmerkmal überzeugender als der Pfeil. Was ihn trennt, ist **wo er liegt** (Surround, wo keine Spitze stecken kann).
- **Strukturdifferenz statt Intensitätsdifferenz** (Varianz / NCC) — die eigentlich passende Größe für schwarz-auf-schwarz: ein Pfeil, der ein Sisal-Bett verdeckt, ändert dessen *Textur*, auch wenn er den Mittelwert nicht ändert.
- **Kamerawackeln ist nicht das Problem** (gemessen): 276/285 Paare bewegen sich unter 2 px, kein Zusammenhang zwischen Bewegung und Fehler. Gilt aber nur für die still aufgestellte Kamera, nicht für freihändig.
- **Verdeckung** aktuell nur implizit gelöst.
- **Laufzeit** pro Detektion noch nicht systematisch gemessen.
- **Testdaten-Aufnahme im laufenden Spiel** geplant: der Server hat beim Scoren bereits alles (Frames + Referenz + Kalibrierung), der Spieler korrigiert am Visit-Ende auf einem klickbaren Board. **30 Visits = 90 beschriftete Paare an einem Abend** gegen den heutigen Handbetrieb.

---

## 9. Fragen zu Arbeit & Scope

- **Negativergebnisse:** wie viel Gewicht in 15–25 Seiten? Ich habe deutlich mehr verworfene als übernommene Ansätze, und die Systematik dahinter (§5c, §7) halte ich für das stärkere Ergebnis als die 79.6 %.
- **Metrik:** exaktes Segment ist streng, die Hälfte der Fehler liegt unter 5 mm — zusätzlich mm-Distanz- oder „within-1-Sektor"-Metrik ausweisen?
- **Baseline:** reicht die eigene Progression (18 → 80 %), oder externer Bezug (kommerzielles Autoscoring / publizierte Methode) erwartet?
- **Stichprobe:** 285 Paare / 5 Boards / 16 Setups — genug? Board-Aufschlüsselungen beruhen teils auf 30 Paaren, dort ist ein einzelner Pfeil schon Rauschen.
- **Scope bei knapper Zeit:** Breite (mehr Bedingungen messen) oder Tiefe (Korridor-Wachstum implementieren)? Einreichung 31.08.
- **Gelernter Tip-Detektor** vs. klassisches Verfahren weitertreiben — passt ein Lern-Ansatz überhaupt in den Rahmen, oder ist das ein anderer Arbeitstyp?
