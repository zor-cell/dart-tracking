# Stichwortzettel – Zwischenstand

## Kalibrierung – Bild → Board

**Ergebnis:** 3×3-**Homographie**, bildet Bildpixel → Board-Millimeter. Basis für *alles* Weitere.

- **Homographie = Ebene→Ebene**, 8 Freiheitsgrade, das ortsabhängige `w` erzeugt die perspektivische Verkürzung.
- **Grenzen:** gilt nur für Board-Ebene (Schaft/Flight ragen raus), an Kamerapose gebunden, kennt keine Objektivverzeichnung.

**Pipeline (6 Schritte):**
1. **HSV-Farbsegmentierung** → rot/grün-Maske. Warum HSV: Helligkeit vom Farbton getrennt → robust gegen Licht. Rot braucht 2 Bereiche (Hue-Umschlag).
2. **Board-Auswahl per Zwei-Ring-RANSAC** — der Kern-Trick.
3. **Ellipsen-Fit** über Convex Hull → Außenkante Double-Ring (170 mm bekannt).
4. **Ring-Walk** → Farbübergänge = Sektordrähte (bekannte Winkel).
5. **Zuordnung** → 20 Punktkorrespondenzen.
6. **Homographie-Fit**, dann Mittelpunkt neu schätzen ↺ (Schleife).

**Der entscheidende Gedanke (Schritt 2):**
- Fitten allein ist wehrlos — *jeder* Ausreißer zieht mit (Stuhl, Nummern, Branding fallen in rot/grün).
- Stattdessen **hypothetisieren statt fitten:** Board vorschlagen, zählen wer zustimmt (RANSAC, 800 Iterationen).
- **Modell ist ein ganzes Board:** zwei konzentrische Ringe, beide **alternieren rot/grün**. → das trennt Board von Clutter (aller Störer ist *einfarbig*).
- Stimme pro Komponente, nicht pro Pixel (sonst überstimmt der fette Triple-Ring).

**Ring-Walk-Gedanke (Schritt 4):** Ellipsen-Parameter ≠ Board-Winkel (nur bei Parallelprojektion). Deshalb echte Korrespondenzen über die *Farbe*: Wechsel exakt an den Drähten. Sampling entlang **Gerade vom Mittelpunkt** (Homographie bildet Geraden auf Geraden ab).

**Zahlen:** erkannt **10/13** (vorher 8/13), Drähte durchgehend 20/20, ~432 ms/Bild.

---

## Pfeil-Erkennung – was hat der Wurf hinzugefügt

**Grundprinzip:** Pfeil *nicht* am Aussehen erkennen (dunkel+dünn auf dunklem Board = schwaches Signal), sondern **Frame-Differenz** — das Neue.
- Differenz gegen **vorherigen Frame**, nicht gegen leeres Board → alte Pfeile heben sich auf. **Rollender Referenz-Frame.**

**Pipeline (5 Schritte):**
1. **Registrierung (ORB, board-maskiert)** — neuen Frame auf Referenz warpen. Handkamera driftet: 25 px Versatz = ~117 000 falsche Pixel. Maske aufs Board, weil Board/Wand verschiedene Tiefen (sonst rastet Fit auf Wand ein).
2. **Differenz + Schwellwert + Cleanup** — pro Farbkanal, dann max (schwarzer Barrel vor schwarzem Segment unterscheidet sich in *Farbe*, nicht Helligkeit). Erst Speckle weg, dann Lücken schließen.
3. **Fragment-Fusion** — schwarzer Pfeil difft nur über *hellem* Board → kommt in Bruchstücken. Fragmente auf einer Geraden zusammenfügen, **Flight = breitestes Fragment = Anker**. Längen-Cap (90 mm) war größter Einzel-Hebel.
4. **Hauptachse (PCA) + Spitze** — Spitze = Ende **gegenüber dem Flight** (formbasiert, nicht „zentrumsnächstes Ende").
5. **Scoring** — Spitze durch Homographie → mm → Segment (reine Geometrie).

**Zahlen / Genauigkeits-Verlauf (60 Wurf-Paare, Ground Truth):**
- Baseline (größter Blob) **18.3 %** → +Flight-Orientierung 21.7 % → +Fragment-Fusion 48.3 % → +Längen-Cap **61.7 %**.
- Restfehler fast nur Nachbar-Segment (wenige mm daneben), nur 4 echte MISS.
- **Ursache Restfehler = das Signal, nicht der Algorithmus:** schwarze Pfeile sind pathologisch (schwarz auf schwarz ≈ 0 Differenz). Schwellwert senken half nicht (Negativergebnis gemessen).

---

## Wissenschaftlicher Prozess – verworfene Ansätze (gute Talking Points)
- **Hough-Kreis** (Konzept-Draft): schräges Board = Ellipse, kein Kreis. Ellipsen-Hough = 5D-Akkumulator, zu teuer.
- **Erscheinungsbasierte Pfeil-Detektion** (Draft: Hough-Linien/Kontur): findet auch die Sektordrähte. Differenz ist stärkeres Signal → grundlegender Richtungswechsel ggü. Konzept.
- **Differenz gegen leeres Board:** alle Pfeile leuchten auf. Deshalb gegen Vorframe.
- **Morphologisches Opening gegen Speckle:** kleinstes Element 3×3 = breiter als Pfeil, warf 60 % Pfeil-Pixel weg → stattdessen Flächengrenze.

## 5. Offene Punkte / nächste Schritte
- **Signal statt Algorithmus:** Setup mit helleren Pfeilen messen → isoliert, wie viel Restfehler am Front-End liegt.
- **Beleuchtungsvarianz:** HSV-Grenzen fest, unterbelichtete Bilder fallen durch (Phase 3).
- **Objektivverzeichnung** unmodelliert (Randfehler).
- **Board-Clear / Re-Base:** rollender Referenz-Frame kennt kein „Pfeile gezogen"-Signal.
- **Unabhängige Genauigkeitsmessung** der Kalibrierung (±0.2 mm ist nur Fit-Residuum).

## Zeitplan
- Phase 1–2 (Setup, Core/MVP) abgeschlossen. Aktuell **Phase 3/4** (Robustheit + Evaluation). Einreichung 31.08.

---

## Follow-ups / was ich besprechen will

### Meine Punkte (geschärft)
- **Kontrastreichere Pfeile / schwarze Spitzen.** Dominanter Restfehler = farb-gegatetes Signal des schwarzen Pfeils. → Zählt „Bedingungen charakterisieren, unter denen die Methode trägt" (helle Pfeile messen, schwarze als *hard case*) als eigenständiges Ergebnis, oder soll ich schwarz-auf-schwarz algorithmisch lösen (gelernter Tip-Detektor)?
- **Shared Rooms.** Homographie ist *pose-gebunden* → Tippen am Stativ bewegt die Kamera, killt die Kalibrierung. Shared Rooms entkoppeln Steuergerät und Kamera. → Aufwand im Rahmen der Arbeit, oder Wackeln als Limitation dokumentieren + Drift-Erkennung als CV-Antwort andiskutieren?

### Evaluation / Wissenschaftlichkeit
- **Baseline:** reicht Vergleich gegen eigene Progression (18 → 63 %), oder externer Bezug (kommerzielles Autoscoring / publizierte Methode) erwartet?
- **Metrik:** exaktes Segment ist streng, die meisten Fehler sind Nachbar-Sektor (wenige mm). Zusätzlich mm-Distanz- oder „within-1-Sektor"-Metrik?
- **Kalibrier-Genauigkeit:** aktuell nur Fit-Residuum (±0.2 mm) — Punkte außerhalb des Fits (Triple-Ring) für belastbare Zahl nötig?
- **Stichprobe:** 135 Paare, 2 Boards — genug, oder mehr Boards/Licht für statistische Aussagekraft?

### Scope / Abgrenzung
- **Verdeckung:** aktuell nur implizit — explizites Handling in-scope oder als Limitation?
- **Objektivverzeichnung:** einmalige Intrinsics-Vorkalibrierung wert, oder außerhalb der Arbeit?
- **Laufzeit-Rekalibrierung / Drift-Erkennung:** MVP oder Future Work?

### Technische Richtung (Zeit-Trade-off)
- **Gelernter Tip-Detektor** (Ground-Truth-Infra existiert) vs. kantenbasiertes Front-End — was passt in Zeitrahmen + Arbeit?
- **3D-lite Extrapolation** (`H = K·[r₁ r₂ t]`, Pfeillänge mit Board-Ebene schneiden): versuchen oder als Ausblick?

### Schreiben / Struktur
- **Verworfene Ansätze:** wie viel Gewicht? (Zeigt Prozess, kann aber 15–25 Seiten sprengen.)
- **CV-Theorie-Tiefe:** Homographie/RANSAC/Morphologie erklären vs. voraussetzen?
- **Hybrid-Architektur:** eigenständiger Beitrag zum Hervorheben, oder Engineering-Detail?

### Zeitplan
- Phase 3 (Robustheit) vs. Phase 4 (Eval): bei knapper Zeit — Breite (mehr Bedingungen) oder Tiefe (schwarz-auf-schwarz fixen)? Größter Payoff? Auf Kurs für 31.08., was ggf. streichen?
