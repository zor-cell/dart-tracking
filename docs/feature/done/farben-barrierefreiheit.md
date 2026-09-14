# Farben und Farbfehlsichtigkeit

Die Farben, die Nutzer über dem Kamerabild und auf der virtuellen Scheibe
sehen: die drei Dart-Farben einer Runde und die Linien des Board-Modells nach
der Kalibrierung. Anlass war der Hinweis des Betreuers, dass die alte Palette
für Farbfehlsichtige ungeeignet ist.

Referenz-Implementierung: `frontend/src/app/features/game/models/dart-colors.ts`,
`frontend/src/app/features/calibration/components/overlay/overlay.component.ts`.

---

## 1. Die zwei Probleme

**Unterscheidbarkeit.** Die Farben müssen untereinander auseinanderzuhalten
sein, auch bei Protanopie, Deuteranopie und Tritanopie. Die alte Palette
(Cyan / Pink / Lime, Board-Linien Gelb) versagte hier in mehreren Paaren.

**Kontrast gegen den Untergrund.** Gezeichnet wird auf ein Dartboard, und das
hat vier Untergründe gleichzeitig: schwarz, creme, rot, grün. Keine einzelne
Farbe erreicht gegen alle vier das WCAG-Minimum für Grafiken (1.4.11, 3:1) — eine
helle Farbe verschwindet auf Creme, eine dunkle auf Schwarz. Gemessen erreichte
**keine** der geprüften Farben auf Creme mehr als 3.2:1, die meisten lagen bei
1.1 – 2.1.

Rot und Grün scheiden als Dart-Farben ohnehin aus: es sind die Farben der
Double- und Triple-Felder.

## 2. Messverfahren

Script im Scratchpad, nicht im Repo (einmalige Auswahl, keine laufende Metrik):

- **Simulation** der drei Dichromasien nach Machado et al. (2009), Schweregrad
  1.0, angewandt in linearem sRGB.
- **Abstand** je Farbpaar als euklidische Distanz in OKLab (×100). Maßgeblich
  ist das *schlechteste* Paar über alle Sehtypen — eine Palette ist nur so gut
  wie die zwei Farben, die am ehesten verwechselt werden.
- **Kontrast** nach WCAG 2.x (relative Luminanz).

## 3. Ergebnis

Kleinster Paarabstand (OKLab ×100) über alle vier Farben (drei Darts + Board-Linien):

| Palette | normal | Protan | Deutan | Tritan |
|---|---|---|---|---|
| alt: Cyan / Pink / Lime + Gelb | 19.2 | **7.5** | 10.4 | **4.7** |
| Okabe-Ito: Himmelblau / Orange / Rotviolett + Weiß | 20.0 | 13.7 | 9.6 | 8.5 |
| Himmelblau / Gelb / Magenta + Weiß | 19.8 | 21.0 | 16.5 | 11.0 |
| Himmelblau / Gold / Rosa + Weiß | 22.3 | 5.1 | 11.1 | 4.4 |
| **IBM: Blau / Amber / Magenta + Weiß** | **25.3** | **22.8** | **19.8** | **22.3** |

Die alte Palette verwechselte bei Protanopie den dritten Dart (Lime) mit den
gelben Board-Linien, bei Deuteranopie Dart 1 und 2, bei Tritanopie Dart 1 und 3.

Gewählt: die Palette aus der IBM Design Library, `#648fff` / `#ffb000` /
`#dc267f`. Sie ist die einzige, die in allen vier Sehtypen einen Mindestabstand
von rund 20 hält.

### Board-Linien: Weiß, dünn

Weiß ist rechnerisch am weitesten von den Dart-Farben entfernt und unbunt, also
für jeden Sehtyp gleich. Im Kamerabild wirkte es bei 1.5 px aber zu dominant und
lag nah an den silbernen Drähten des Boards. Geprüft wurden deshalb Alternativen,
mit dem Abstand zum Drahtsilber (`#c8c8c8`) als zweitem Kriterium:

| Farbe | min. Abstand zu Darts (alle Sehtypen) | Abstand zum Draht normal / Protan / Deutan / Tritan |
|---|---|---|
| Weiß `#ffffff` | 24.2 | 16.7 / 16.7 / 16.7 / 16.7 |
| **Cyan `#00e5ff`** | **20.1** | **14.6** / 8.0 / 8.2 / 15.2 |
| Gelbgrün `#d4ff00` | 11.1 | 24.8 / 22.3 / 21.2 / 11.3 |
| Gelb `#ffe600` | 9.9 | 20.9 / 19.9 / 20.6 / 8.8 |
| Türkis `#00c9a7` | 10.2 | 16.6 / 5.1 / 8.9 / 15.1 |
| Violett `#b388ff` | 1.2 | 20.7 / 20.2 / 19.7 / 12.6 |

Cyan war die beste Alternative, wurde im Bild aber verworfen. Es bleibt bei
**Weiß**, die Linien des Board-Modells sind dafür von 1.5 auf **1 px** verschlankt.

## 4. Kontur: erprobt, wieder entfernt

Das Kontrastproblem aus §1 löst keine Palette, sondern nur eine **dunkle Kontur**
unter jeder Linie. Mit `#1b1b1b`, 2 px breiter als die Linie, läge alles über
3:1:

| | Kontrast |
|---|---|
| Kontur gegen Creme / Rot / Grün | 12.1 / 3.2 / 3.7 |
| Blau / Amber / Magenta / Weiß gegen Kontur | 5.7 / 9.4 / 3.8 / 17.2 |

Im Kamera-Overlay tragen sie nur die **Darts**: Linie und Nummer bekommen dieselbe
Kontur wie die Marker der virtuellen Scheibe, damit beide Ansichten gleich
aussehen. Die Board-Modell-Linien bleiben ohne Kontur und liegen auf Creme damit
weiter unter 3:1.

## 5. Nicht nur Farbe

WCAG 1.4.1 verlangt, dass Farbe nicht das einzige Unterscheidungsmerkmal ist.
Deshalb zusätzlich:

- **Ordinalzahl am Dart** auch im Kamerabild (neben der Spitze), wie auf der
  virtuellen Scheibe bereits vorhanden.
- **Linienstärke**: Dart-Linien 1.5 px, Board-Modell 1 px. Auch ohne Farbe ist
  erkennbar, was Modell und was Treffer ist.

## 6. Offen

- Die Kalibrierungs-Debugbilder (`debug/render.py`) nutzen weiter ihre eigenen
  Farben. Die sind Entwicklerwerkzeug und nicht Teil der Oberfläche.
- Die Statusfarben im Wurf-Log (`game.component.scss`: blau / grün / rot) sind
  nicht geprüft.
- Gemessen ist die Simulation, nicht ein Nutzertest mit Betroffenen.
