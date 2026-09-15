# Der Pfeil muss als ein Blob ankommen

Arbeitsdokument zu der einen Fehlerursache, die unter allen anderen liegt: der
Pfeil erreicht die Auswertung nicht als **ein** zusammenhängendes Objekt, sondern
als Streu-Fragmente, die `_fuse_dart_fragments` hinterher wieder zusammenraten
muss. Alles, was danach kommt — Anker-Wahl, Achsenfit, Spitzen-Präzision — ist
Schadensbegrenzung an diesem einen Punkt.

Pipeline-Beschreibung: [erkennung.md](done/erkennung.md). Geplante Einzelschritte:
[erkennung-verbesserungen.md](erkennung-verbesserungen.md). Dieses Dokument ist
kein Schritt in jener Liste, sondern das Ziel, auf das die Liste hinauslaufen
soll.

---

## 1. Die Ausgangsthese

**Ein Mensch sieht den Pfeil.** Auf jedem Bild des Testsatzes ist der Pfeil vom
Bett, in dem er steckt, farblich zu unterscheiden — auch schwarz auf schwarz, auch
weißer Flight auf beigem Bett. Die Information steckt also im Bild. Wenn die
Änderungsmaske den Pfeil trotzdem in Bruchstücke zerlegt, ist das eine Eigenschaft
des Front-Ends, keine Eigenschaft der Aufnahme.

Daraus folgt das Ziel, an dem sich jede weitere Änderung messen lassen muss:

> **Eine Detektion = eine zusammenhängende Komponente**, über alle Betten hinweg,
> die der Pfeil kreuzt — Spitze im schwarzen Single, Barrel über dem beigen,
> Flight über dem Surround.

Das ist eine stärkere Forderung als „mehr Accuracy". Sie ist auch direkt messbar,
unabhängig vom Scoring: Anzahl der Komponenten, aus denen der gewertete Pfeil
zusammengesetzt wurde, und ob die Spitze in der größten davon liegt.

---

## 2. Warum das der zentrale Punkt ist

Die Fusion ankert auf dem **breitesten** Fragment und nennt es Flight
([erkennung.md §2.3](done/erkennung.md#23-fragment-fusion-den-pfeil-aus-bruchstücken-zusammensetzen)).
Diese Regel ist nur haltbar, solange die Maske im Wesentlichen aus Pfeil besteht.
Sobald sie auch Fremdmaterial enthält — Registrierungs-Residuen an Drähten, die
weißen Board-Zahlen, Branding auf dem Surround — konkurriert jedes breite,
helle Fremdfragment um den Anker, und der Anker entscheidet den ganzen Fit.

Belegt an `pz-light_setup2/throw8/dart1` (Zwischenstand dieses Laufs, gelockerter
Schwellwert): **144 Komponenten**, der Anker sitzt auf dem BLADE‖6-Schriftzug am
unteren Surround, der echte Pfeil steckt auf 10 Uhr. Ergebnis `MISS` bei
r = 196 mm.

Daraus folgt eine unbequeme Kopplung, die diesen ganzen Lauf erklärt:

> Solange der Anker „breitestes Fragment" heißt, **verschlechtert jede Änderung,
> die die Maske größer macht, das Ergebnis** — auch wenn sie mehr echtes
> Pfeil-Signal einsammelt.

Genau das ist unten viermal hintereinander gemessen worden.

---

## 3. Was dieser Lauf gemessen hat

Ausgangsstand **218/285 = 76.5 %**, Endstand **222/285 = 77.9 %**. Alle Zahlen mit
`scripts/detection/run_all.py` über die vollen 285 Paare, Metrik wie in
[erkennung.md §3](done/erkennung.md#no_change-ist-punktemäßig-ein-miss).

### 3.1 Ortsabhängiger Schwellwert — verworfen

[erkennung-verbesserungen.md §3](erkennung-verbesserungen.md#3-ortsabhängiger-schwellwert-hsv-für-helle-betten)
hatte gemessen, dass auf schwarzem Bett nur **38 %** der Pfeil-Pixel den globalen
Schwellwert von 40 überschreiten, gegen 90 % auf hellem — bei einem
Signal-Untergrund-Verhältnis von 9.9× (max\|ΔBGR\|) bzw. 12.8× (ΔV). Der
naheliegende Schluss: der Schwellwert ist auf schwarzem Bett zu streng und muss
ortsabhängig werden.

**Umgesetzt** als Schwellwert-Karte, deren beide Enden pro Frame vom Board selbst
abgelesen werden: die Homographie liefert die Mittelpunkte aller schwarzen und
aller beigen Single-Betten (`single_bed_centres()`), dort wird die geglättete
Max-Kanal-Helligkeit der Referenz gemessen, und dazwischen wird linear
interpoliert — schwarzes Bett bekommt `_MIN_DIFFERENCE_THRESHOLD`, beiges die
unveränderten 40. Kein fester Grauwert, keine angenommene Pfeilfarbe.

Die Vormessung bestätigt, dass eine feste Grenze ausgeschlossen ist (Max-Kanal,
3 mm geglättet, mittig im Bett abgetastet):

| Setup | schwarz | beige | Setup | schwarz | beige |
|---|---|---|---|---|---|
| tz_setup1 | 3.2 | 135.9 | pz_setup4 | 27.4 | 205.0 |
| tz_setup2 | 7.4 | 167.8 | pz_setup2 | 28.2 | 205.9 |
| tz_setup3 | 7.6 | 153.4 | pz-light_setup2 | 36.6 | 216.9 |
| tz_setup4 | 8.9 | 167.9 | pz-light_setup3 | 44.6 | 225.7 |
| pz_setup1 | 10.8 | 166.6 | cc_setup1 | 47.8 | 222.7 |
| tz_setup5 | 16.8 | 189.2 | pz-light_setup1 | 49.5 | 228.3 |
| pz_setup3 | 17.7 | 183.3 | cc_setup2 | 54.5 | 222.8 |
| fh_setup1 | 26.7 | 171.6 | fh_setup2 | 27.6 | 180.0 |

Das *beige* Bett von `tz_setup1` (135.9) ist dunkler als das *schwarze* keines
Setups, aber der Abstand innerhalb eines Frames ist immer eindeutig — die
Selbstkalibrierung funktioniert, der Schwellwert nicht.

**Vier Varianten, je drei Werte, alle unter der Baseline:**

| Variante | min 10 | min 16 | min 24 | 40 (= aus) |
|---|---|---|---|---|
| A: bettskalierter Schwellwert | 151 | 197 | 211 | **218** |
| B: + Seed-Hysterese (40 sät, locker wächst) | 181 (bei 8) | 204 | 213 | **218** |
| C: + nur innerhalb der Scoring-Fläche | 199 | 210 | 217 | **218** |
| D: + nur für dunkler werdende Pixel | 209 | 213 | 217 | **218** |

**In keiner Variante gibt es ein Maximum im Inneren.** Die Quote fällt monoton mit
jeder Lockerung; das Optimum liegt jedes Mal exakt dort, wo die Änderung nichts
mehr tut. Das ist kein Parameterproblem, das ist ein Strukturproblem.

Jede Zeile hat dabei eine echte Fehlerursache beseitigt, und trotzdem:

- **B** (Hysterese) ist die Lehre aus
  [erkennung.md §5.11](done/erkennung.md#511-gradientenabhängiger-schwellwert-gegen-registrierungs-reste),
  korrekt herum angewandt: der strenge Schwellwert entscheidet *ob* etwas eine
  Änderung ist, der lockere nur *wie weit* sie reicht. Bringt +7 gegenüber A,
  bleibt 14 unter der Baseline.
- **C** streicht die Lockerung im Surround, wo ohnehin nichts zu werten ist und
  die Zahlen und das Branding sitzen. Nochmals +6, immer noch 8 unter.
- **D** lockert nur, wo der Frame *dunkler* geworden ist — die physikalische
  Begründung, dass eine Differenz nur nach unten durch die Bett-Helligkeit
  begrenzt ist. Nochmals +3, immer noch 5 unter.

**Aufschlüsselung nach Board** (Baseline: `pz-light` 74/90, `cc` 23/30, `fh` 23/30,
`pz` 44/60, `tz` 54/75):

| Variante | tz | pz | cc | pz-light | fh |
|---|---|---|---|---|---|
| A, min 24 | **57** | 43 | 19 | 69 | 23 |
| A, min 16 | 53 | **47** | 16 | 59 | 22 |
| C, min 16 | 55 | **50** | 15 | 68 | 22 |
| D, min 16 | 56 | 43 | 22 | 69 | 23 |

Die Boards mit **dunklen Pfeilen** (`tz`, `pz`) gewinnen genau das, was die
Vormessung versprochen hat — `pz` bis zu **+6** (44 → 50, 73 % → 83 %). Die Boards
mit **Wolfram-Pfeilen** (`cc`, `pz-light`, `fh`) verlieren mehr, als jene gewinnen.
Der Gewinn ist real, er ist nur nicht einzusammeln, ohne anderswo mehr zu
zerstören.

**Nebenbefund, der noch zu verifizieren ist.** Der `pz`-Gewinn von Variante C
(50) verschwindet in Variante D (43), und D unterscheidet sich von C *nur* dadurch,
dass die Lockerung auf dunkler werdende Pixel beschränkt ist. Die Pixel, die den
dunklen Pfeil auf schwarzem Bett sichtbar machen, sind demnach **heller** als das
Bett, nicht dunkler: ein matter Sisal-Bett gegen einen glänzenden Barrel — der
Pfeil zeigt sich dort über seinen **Glanz**, nicht über seine Dunkelheit. Das ist
aus einem A/B-Paar geschlossen, nicht direkt gemessen; die direkte Messung
(Vorzeichen der Kanaldifferenz entlang der Achse korrekt gewerteter Würfe auf
schwarzen Betten) steht aus. Falls es sich bestätigt, ist es ein handfester Hebel:
das Merkmal wäre spekulare Reflexion, nicht Albedo.

Der Code dieser Variante ist **nicht** übernommen.

### 3.2 Sättigungskanal auf hellen Betten — übernommen

Der zweite Teil von Schritt 3 hält dagegen. Befund war: ein weißer Flight über
beigem Bett unterscheidet sich in **BGR** um etwa 14 Grauwerte — unter dem
Schwellwert von 40, also unsichtbar — in der **Sättigung** aber um rund 29. Der
Kanal, der diese Unterscheidung trägt, wurde schlicht nicht ausgewertet.

**Umgesetzt** als zweiter Kanal neben `max|ΔBGR|`: `absdiff` auf dem S-Kanal,
verodert mit der bisherigen Maske. Entscheidend ist das Gate — S ist nur dort
belastbar, wo das Bett hell ist (`S = (max−min)/max` ist über schwarzem Bett
rechnerisch verrauscht, gemessenes Verhältnis nur 2.4× gegen 13.3× auf hellem
Bett). Das Gate benutzt dieselbe Selbstkalibrierung wie oben: liegt ein Pixel
über 60 % des Weges vom schwarzen zum beigen Bett, zählt der S-Kanal, sonst nicht.

| ΔS-Schwelle | gesamt | tz | pz | cc | pz-light | fh |
|---|---|---|---|---|---|---|
| — (Baseline) | 218 | 54 | 44 | 23 | 74 | 23 |
| 20 | 205 | 54 | 37 | 18 | 75 | 21 |
| **30** | **222** | **55** | **45** | 23 | **76** | 23 |
| 45 | 218 | 54 | 44 | 23 | 74 | 23 |

**222/285 = 77.9 %**, und **kein Board verliert** — das erste Ergebnis dieser
Reihe, das das schafft. Die Zeile bei 45 ist die Kontrolle: dort ist der Kanal
faktisch aus und reproduziert die Baseline pro Board exakt, die Implementierung
ändert also nichts außer dem, was sie ändern soll.

Bei 20 kippt es (205): auf einem beigen Bett mit ohnehin hoher Sättigung (`fh`
misst 103, `pz` 73) rauscht ΔS über die Schwelle. Auch dieser Kanal braucht also
eine Grenze, die *über* dem Bett-Rauschen liegt — der Unterschied zu §3.1 ist,
dass es hier eine gibt, die auf allen fünf Boards gleichzeitig funktioniert.

**Die Fehlerverteilung bewegt sich dabei kaum:**

| | ≤5 mm | 5–20 | 20–50 | >50 | Mittel | Max |
|---|---|---|---|---|---|---|
| Baseline | 32 | 12 | 5 | 17 | 34.9 | 220.0 |
| mit S-Kanal | 30 | 12 | 4 | 16 | 34.6 | 220.0 |

Vier Pfeile, verteilt über alle Klassen, und der strukturelle Schwanz (>50 mm)
schrumpft um genau einen. **Der Kanal repariert Präzision, nicht Struktur.** Das
eigentliche Problem ist unberührt.

---

## 4. Der gemeinsame Nenner

Vier Varianten, die alle etwas Richtiges tun, und alle vier verlieren. Der
gemeinsame Nenner ist nicht der Schwellwert, sondern **wo** er gelockert wurde:
über der gesamten Suchfläche.

Die Suchfläche hat bei 1 px/mm rund 300 000 Pixel. Ein Pfeil hat ein paar hundert.
Eine Lockerung, die auf der ganzen Fläche gilt, kauft ein paar hundert echte
Pfeil-Pixel gegen zehntausende Fremdpixel — und weil der Anker „breitestes
Fragment" heißt, genügt **ein** breites Fremdfragment, um den kompletten Fit zu
entführen. Das Verhältnis kann nicht aufgehen.

Die Lockerung wäre aber völlig unproblematisch, wenn sie nur dort gälte, wo ein
Pfeil überhaupt sein kann: in einem 4 mm breiten Korridor entlang einer bereits
belegten Pfeilachse. Dort ist die Fläche um drei Größenordnungen kleiner, und
dieselbe Schwelle von 16 hätte fast nichts anzuziehen.

**Das ist die Schlussfolgerung dieses Laufs:** die Schwelle war nie das Problem,
die *Reihenfolge* war es. Erst schwellen, dann ein Objekt suchen, heißt jede
Lockerung global bezahlen. Erst ein Objekt hypothetisieren, dann in seinem
Korridor lockern, heißt sie fast umsonst bekommen — dieselbe
Hypothetisieren-und-zählen-Logik, die bei der Kalibrierung den Board-RANSAC trägt
([kalibrierung.md §2.2](done/kalibrierung.md#22-board-auswahl-per-zwei-ring-ransac)).

---

## 5. Was der Mensch benutzt und die Pipeline nicht

Wenn ein Mensch den Pfeil auch dort sieht, wo die Maske ihn verliert, benutzt er
Merkmale, die im Front-End gar nicht vorkommen. Der Reihe nach, mit dem Stand der
Pipeline daneben:

| Merkmal | Mensch | Pipeline heute |
|---|---|---|
| **Geradheit / Starrheit** | integriert über die ganze Länge, überbrückt Lücken | erst *nach* dem Schwellwert, in `_fuse_dart_fragments` |
| **Silhouetten-Kante** | sieht die Grenze auch bei gleichem Mittelwert | nur Intensitätsdifferenz pro Pixel |
| **Textur** | Pfeil verdeckt die Sisal-Faserung | gar nicht ausgewertet |
| **Glanz** | matt vs. spekular, auch bei gleicher Farbe | implizit in `max\|ΔBGR\|`, ungerichtet |
| **Farbton** | trennt beige/weiß und schwarz/dunkelgrau | S-Kanal seit §3.2, nur auf hellen Betten |
| **Schatten** | Beleg für ein Objekt, auch wenn es unsichtbar ist | zählt als Störung |
| **Anzahl** | weiß, dass genau ein Pfeil dazugekommen ist | implizit angenommen, nie geprüft |

Die ersten beiden Zeilen sind die wichtigen. **Geradheit** wird heute erst
verwendet, nachdem der Schwellwert entschieden hat — also nachdem die Information
weg ist. **Kante statt Fläche** ist die Antwort auf schwarz-auf-schwarz: zwei
Flächen können denselben Mittelwert haben, ihre Grenze ist trotzdem sichtbar,
und die Grenze ist alles, was man für eine Silhouette braucht.

---

## 5b. Vier Anläufe auf denselben Punkt, vier Fehlschläge

Das ist inzwischen kein Pech mehr, sondern selbst ein Ergebnis. Alle vier haben
an derselben Stelle angesetzt — an der **pro-Pixel-Entscheidung über die gesamte
Suchfläche** — und alle vier sind gescheitert, drei davon mit *monoton* fallender
Quote, das Optimum jedes Mal bei „Änderung aus":

| Anlauf | Idee | Ergebnis |
|---|---|---|
| [erkennung.md §5.10](done/erkennung.md#510-schwellwert-senken-um-das-schwarz-signal-zu-heben) | Schwelle global senken | 40 = 20, bei 12 Absturz |
| [§5.11](done/erkennung.md#511-gradientenabhängiger-schwellwert-gegen-registrierungs-reste) | Schwelle am Gradienten koppeln | +3 gesamt, −2 auf `fh` |
| [§5.12](done/erkennung.md#512-bettskalierter-schwellwert-verworfen) | Schwelle am Bett koppeln | 4 Varianten, alle unter Baseline |
| [§5.14](done/erkennung.md#514-anderer-differenz-kanal-δv-statt-maxδbgr-verworfen) | anderen Kanal wählen | schlechter auf **jedem** Wert |

Der vierte ist der lehrreichste, weil er die Vormessung gegen sich hatte: ΔV
gewann im Signal-zu-Untergrund-Verhältnis **jedes einzelne Feld** und verlor
trotzdem neun Pfeile. Zwei übertragbare Lehren:

- **Das Verhältnis ist nicht die Entscheidungsgröße, solange die Schwelle fest
  ist.** Verliert ein Kanal Absolutsignal, nützt der bessere Rauschabstand
  nichts — der feste Schnitt bei 40 fragt nach dem Absolutwert.
- **Man muss das richtige Rauschen messen.** Die 40 sind nicht durch
  Sensorrauschen gesetzt (Kontrolle 2–4), sondern durch Registrierungs-Reste an
  Kanten (§5.11: Gradient 52 Grauwerte/Pixel). Jede Maßnahme, die nur das
  Sensorrauschen senkt, verfehlt die Störquelle.

Damit ist §4 nicht mehr eine Schlussfolgerung aus einem Lauf, sondern aus vieren:
**die Reihenfolge ist das Problem, nicht der Wert und nicht der Kanal.**

Was von der Vormessung *gültig bleibt*, ist die Diagnose — und sie ist scharf:

> **Die Pfeilspitze liegt auf schwarzem Bett im Median bei 39.0 Grauwerten, bei
> einer Schwelle von 40.**

Die Hälfte der Spitzenpixel fällt um einen Grauwert durch, und die Spitze ist der
einzige Teil, auf den es fürs Scoring ankommt. Sichtbar ist das auch direkt: in
den Differenzbildern (`_results_probe/differences/`) ist das Signal entlang des
Pfeils stark abgestuft — Schaft hell, Flight mittel, **Spitze verläuft ins
Nichts**. Genau diesen Fall adressiert §6.2, und zwar an der Stelle, an der die
Fläche klein genug ist, um die Lockerung zu bezahlen.

---

## 6. Arbeitsplan

Reihenfolge nach Hebel geteilt durch Risiko. Jeder Schritt einzeln gegen die
285 Paare gemessen, sonst gilt er nicht als erledigt.

### 6.1 Anker entkoppeln (S)  *(als Umsortierung verworfen)*

Die Anker-Regel ist der Multiplikator hinter jedem Fehlschlag oben. Der Anker muss
gar nicht der Flight sein — welches Ende der Flight ist, entscheidet ohnehin erst
`_tip_and_far_end` über die Endbreiten am fertig gefusten Blob
([erkennung.md §2.4](done/erkennung.md#24-hauptachse-und-spitze)). Der Anker muss nur
**mit Sicherheit ein Pfeilfragment** sein.

Kandidat war: nicht das breiteste, sondern das *überzeugendste* Fragment —
Kontrast über dem lokalen Bett-Rauschen, Länglichkeit, Fläche.

**Gemessen, sechs Regeln über die vollen 285 Paare:**

| Anker-Regel | korrekt |
|---|---|
| Breite (Baseline) | 222 |
| Fläche | 222 |
| Fläche × Helligkeit | 222 |
| Breite × Helligkeit | **223** |
| Fläche × Breite | 221 |
| Helligkeit allein | 219 |

**Der Ansatz trägt nicht.** Die ersten drei Zeilen sind nicht bloß ähnlich,
sondern **identisch** — auch in der Aufschlüsselung pro Board und in der Zahl der
einkomponentigen Blobs. Der Grund ist trivial und hätte vorher auffallen können:
das *breiteste* Fragment ist fast immer auch das *größte*. Eine Umsortierung nach
Intensitäts- und Formmerkmalen wählt schlicht dasselbe Fragment.

Die ±2 Streuung um die Baseline ist Rauschen, kein Signal; die +1 von
„Breite × Helligkeit" rechtfertigt keinen zusätzlichen Parameter. Übernommen wird
nichts, die Regel bleibt „breitestes Fragment".

**Was das über die Fehlschläge sagt.** Die Anker-Entführung ist real — belegt an
`pz_setup1/throw5/dart1` (0.67 px/mm): der Pfeil sitzt bei S7, der Fit ankert auf
dem Registrierungs-Rest der aufgedruckten Board-Zahlen auf 9 Uhr und scort `MISS`
bei r = 214 mm. Nur ist der Störer dort **auch nach jedem geprüften Merkmal das
überzeugendste Fragment**: breit, hell, flächig, länglich. Was ihn vom Pfeil
trennt, ist nicht seine Erscheinung, sondern **wo er liegt** — im Surround, wo
keine Spitze stecken kann. Ein tragfähiger Anker-Test muss also die Board-Geometrie
benutzen (Radius der Fragment-Schwerpunkte über die Homographie), nicht die
Pixelstatistik. Das ist offen.

### 6.1b Fusions-Reichweite: der Deckel war zu eng

**Erledigt, 77.9 % → 79.6 %.** Nicht geplant, sondern beim Nachsehen einzelner
Fehlschläge gefunden — und der größte Einzelhebel seit dem Längen-Cap selbst.

**Befund.** `_MAX_DART_LENGTH_MM` begrenzt, wie weit ein Fragment vom Anker
entfernt liegen darf, um noch mitgefused zu werden. Der Wert stand auf **90 mm**,
begründet mit „großzügig, da sich die sichtbare Ausdehnung eines Pfeils
verkürzt". **Diese Begründung hat das falsche Vorzeichen.** Der Flight steckt
nicht in der Board-Ebene, sondern ragt daraus heraus, *zur Kamera hin* — die
Homographie bildet ihn also **vergrößert** ab, nicht verkürzt. Dieselbe
Parallaxe, die [kalibrierung.md §1](done/kalibrierung.md#was-die-homographie-aussagt)
als Grenze der Homographie nennt, wirkt hier auf die Fusions-Reichweite.

Belegt an `tz_setup5/throw2` (1.64 px/mm), abgelesen an der neuen Konsolenzeile
aus §6.5:

```
dart1  S17 = 17   fused 2 of 2 components (2 in reach), blob 146 x 41 mm   korrekt
dart2  S8  = 8    fused 2 of 3 components (2 in reach), blob 148 x 32 mm   korrekt
dart3  S4  = 4    fused 1 of 3 components (1 in reach), blob  44 x 33 mm   S14 erwartet, 152 mm daneben
```

Die beiden **korrekt** gewerteten Pfeile spannen 146 und 148 mm — der Deckel für
das Einsammeln lag bei 90. Bei `dart3` reicht es nicht mehr: nur **ein** Fragment
liegt überhaupt in Reichweite, gefused wird also **nur der Flight**, und
`_tip_and_far_end` legt die Achse durch einen 44 mm großen Flight-Klumpen. Die
„Spitze" ist dann ein Ende des Flights.

Mit 110 mm liest sich dieselbe Zeile so — der Pfeil kommt vollständig an und die
Wertung stimmt:

```
dart3  S14 = 14   fused 2 of 3 components (2 in reach), blob 166 x 35 mm   korrekt
```

**Sweep über die vollen 285 Paare:**

| Reichweite | korrekt | Quote | pz-light | tz | pz | fh | cc |
|---|---|---|---|---|---|---|---|
| 90 mm (Baseline) | 222 | 77.9 % | 76 | 55 | 45 | 23 | **23** |
| **110 mm** | **227** | **79.6 %** | **78** | **58** | 46 | 23 | 22 |
| 130 mm | 227 | 79.6 % | **78** | **58** | **47** | 23 | 21 |
| 150 mm | 219 | 76.8 % | 76 | 57 | 44 | 23 | 19 |
| 180 mm | 217 | 76.1 % | 76 | 57 | 44 | 23 | 19 |

**Es gibt ein Optimum im Inneren** — und das ist der qualitative Unterschied zu
allen vier Schwellwert-Varianten aus §3.1, wo die Quote monoton fiel und das
Optimum jedes Mal „aus" hieß. Hier ist die Baseline nicht das Maximum; der Wert
war schlicht zu klein gewählt.

**Gewählt: 110 mm.** Gleiche Quote wie 130, aber `cc` fällt monoton mit der
Reichweite (23 → 22 → 21 → 19), und 110 liegt weiter von der Kante bei 150
entfernt. Bei gleicher Messung die konservativere Wahl.

**Preis, offen ausgewiesen:** `cc` verliert einen Pfeil (23 → 22). Drei Boards
gewinnen, `fh` steht still. Bei 30 Paaren je Board ist ein einzelner Pfeil
Rauschen, aber die Richtung ist konsistent mit dem Rest der Spalte und wird
deshalb nicht weggerundet.

**Nebenwirkung auf die Präzision.** Die mittlere Abweichung der einkomponentigen
Blobs fällt von **4.8 mm auf 2.4 mm**: wo ein Pfeil ohnehin als ein Stück ankam,
sitzt die Achse jetzt auf seiner ganzen Länge statt auf einem Teilstück. Der
Deckel hat also nicht nur Fragmente ausgeschlossen, sondern auch Achsen verkürzt.

---

### 6.2 Korridor-Wachstum: zwei Pässe statt einem (M)

Die eigentliche Konsequenz aus §4.

1. **Pass 1, streng.** Maske wie heute (40 + S-Kanal), Fusion wie heute → eine
   Achsen-Hypothese. Muss nicht vollständig sein, nur richtig orientiert.
2. **Pass 2, locker im Korridor.** Entlang dieser Achse ein Band von etwa 8 mm
   Breite und Pfeillänge; nur dort mit dem bettskalierten Schwellwert aus §3.1
   nachschwellen und die neuen Pixel an den Blob anschließen.
3. Achse auf dem gewachsenen Blob neu fitten, Spitze neu bestimmen.

Der Korridor macht genau die Lockerung bezahlbar, die in §3.1 global gescheitert
ist — inklusive der Werte um 16, die auf `pz` +6 gebracht haben. Er ist zugleich
die erste Stelle, an der die **Geradheit** vor dem Schwellwert benutzt wird statt
danach.

Risiko: eine falsch orientierte Hypothese wächst in die falsche Richtung. Deshalb
gehört §6.1 davor, und der zweite Pass darf die Achse nur verlängern, wenn die
neuen Pixel zusammenhängend an den bestehenden Blob anschließen.

### 6.3 Strukturdifferenz statt Intensitätsdifferenz (M)

Für schwarz-auf-schwarz die eigentlich passende Größe. Statt `|I_ref − I_neu|` pro
Pixel eine lokale Statistik über ein kleines Fenster vergleichen: Varianz,
Gradientenbetrag oder normierte Kreuzkorrelation. Ein Pfeil, der ein Sisal-Bett
verdeckt, ändert dessen Textur, auch wenn er den Mittelwert nicht ändert.

Achtung, das ist nah an dem, was in
[erkennung.md §5.11](done/erkennung.md#511-gradientenabhängiger-schwellwert-gegen-registrierungs-reste)
verworfen wurde — dort war der Gradient allerdings der *Störer* (Drahtkanten unter
Sub-Pixel-Versatz), hier wäre er das *Signal*. Der Unterschied ist die Richtung:
NCC vergleicht Struktur mit Struktur und ist gegen einen kleinen Versatz robust,
während ein Gradienten-Schwellwert ihn gerade misst. Vor der Implementierung eine
Vormessung wie in §3.1: Signal auf dem Pfeil gegen Kontrollmessung auf leerem
Bett, pro Bettfarbe.

### 6.4 Glanz gerichtet auswerten (S, abhängig von §3.1)

Falls sich der Nebenbefund aus §3.1 bestätigt, dass der dunkle Pfeil auf schwarzem
Bett *heller* erscheint: das ist ein gerichtetes Merkmal und damit deutlich
selektiver als eine Betragsdifferenz. Erst messen, dann entscheiden.

### 6.5 Blob-Metriken in den Report (S)  *(erledigt)*

Das Ziel aus §1 war nicht messbar. `run_all.py` schreibt jetzt pro Detektion mit,
aus wie vielen Komponenten der gewertete Pfeil gefused wurde und welchen Anteil
die größte davon hält; der Report trägt den Abschnitt **Per blob cohesion**, die
Mismatch-Tabelle zwei zusätzliche Spalten. Die Quote bleibt dabei unverändert —
die Instrumentierung ist neutral, wie sie sein soll.

**Der Ausgangsbefund, zum ersten Mal als Zahl** (Baseline, 90 mm Reichweite):

| Fragmente | korrekt | gesamt | Quote | mittl. Abweichung |
|---|---|---|---|---|
| 1 (ein Blob) | 78 | 96 | 81 % | 4.8 mm |
| 2 | 107 | 135 | 79 % | 6.3 mm |
| 3 – 4 | 31 | 45 | 69 % | 17.5 mm |
| 5+ | 2 | 4 | 50 % | 13.6 mm |

**Nur 96 von 280 Pfeilen (34 %) kommen als eine Komponente an.** Die Quote fällt
mit jeder zusätzlichen Komponente, die mittlere Abweichung steigt auf das
Dreifache. Die These aus §1 ist damit nicht mehr Plausibilität, sondern gemessen.

**Eine der drei vorgeschlagenen Größen taugt nicht.** Der *Abstand zwischen
Anker-Fragment und gewerteter Spitze* trennt nichts: Median **75 mm** bei
korrekten Wertungen gegen **70 mm** bei Mismatches. Der Grund ist Zirkularität —
die Spitze wird als das dem Anker gegenüberliegende Ende des Blobs bestimmt, den
der Anker aufgespannt hat, also misst der Abstand im Wesentlichen die Blob-Länge
und nicht die Güte des Ankers. Die Spalte bleibt trotzdem im Mismatch-Report,
weil ein einzelner Ausreißer (16 mm oder 96 mm) im Einzelfall diagnostisch ist —
als Kennzahl über den ganzen Satz ist sie es nicht.

Dieselben Zahlen stehen auch in der Konsolenausgabe von `run_debug.py`, eine
Zeile je Pfeil. Genau daran ist §6.1b aufgefallen.

---

## 7. Was aus diesem Lauf im Code steht

- `single_bed_centres()` in `board_geometry.py` — die Mittelpunkte aller schwarzen
  und beigen Single-Betten. Von §3.2 benutzt, für §6.2 wieder gebraucht.
- `_saturation_thresholds` / `_saturation` in `dart_detector.py` — der S-Kanal aus
  §3.2 mit seinem Hell-Bett-Gate, `_SATURATION_THRESHOLD = 30`.
- `trace.saturation_only` und dessen Darstellung in `04_threshold.jpg` (gelb):
  welche Pixel *nur* der Sättigungskanal gesehen hat. Ohne das ist der Beitrag
  des Kanals im Bild nicht von dem der Intensität zu trennen.
- `trace.fragment_count` / `largest_fragment_share` / `anchor_to_tip_mm` aus §6.5,
  im Report als Abschnitt *Per blob cohesion* und in `run_debug.py` als
  Konsolenzeile je Pfeil.
- `_MAX_DART_LENGTH_MM = 110.0` aus §6.1b (vorher 90).

Nicht im Code: die Schwellwert-Karte aus §3.1 in allen vier Varianten. Die
Messungen dazu stehen oben und in
[erkennung-verbesserungen.md](erkennung-verbesserungen.md).
